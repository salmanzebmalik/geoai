# pgstac database setup

The STAC database behind the Sentinel-2 layers and the `/sentinel` bbox service.
It is a **rootless** PostgreSQL: the server binaries come from conda, the data
directory lives on the shared volume, and nothing is installed system-wide.

Live install on `geoai`:

```
/home/ubuntu/work/saved_data/postgres_pgstac/
├── miniforge3/          conda root, env "stac" = postgresql 18.4 + postgis 3.6.4
├── pgdata/              the cluster (stac db ~4.6 GB)
└── postgres.log         server log
```

| | |
|---|---|
| host / port | `127.0.0.1:5432` (TCP, localhost only) |
| database | `stac` |
| superuser | `ubuntu` |
| pgstac | 0.9.11, migrated 2026-07-14 |
| PostgreSQL | 18.4 |
| PostGIS | 3.6.4 |

There is a second database `geoai` (owner `geoai_app`) in the same cluster for
the application itself. It is unrelated to pgstac.

## Starting it

Nothing starts the server automatically after a reboot.

```bash
./start_pgstac_db.sh
```

It is a no-op if the server is already up. Then start the tile server:
`image_pipeline/launch_titiler.sh`.

## Recreating it from scratch

### 1. Miniforge

```bash
BASE=/home/ubuntu/work/saved_data/postgres_pgstac
curl -LO https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-x86_64.sh
bash Miniforge3-Linux-x86_64.sh -b -p "$BASE/miniforge3"
```

### 2. PostgreSQL + PostGIS

The one thing pip cannot provide. conda-forge ships both as relocatable
user-space packages, so no root and no Docker.

```bash
"$BASE/miniforge3/bin/conda" create -y -n stac -c conda-forge postgresql postgis
BIN=$BASE/miniforge3/envs/stac/bin
```

### 3. Initialise the cluster

```bash
"$BIN/initdb" -D "$BASE/pgdata"
```

Defaults are kept as-is. `pg_hba.conf` stays stock: `trust` over the unix
socket and `127.0.0.1`/`::1` only, nothing listening externally.

### 4. Start

```bash
"$BIN/pg_ctl" -D "$BASE/pgdata" -o "-p 5432" -l "$BASE/postgres.log" start
"$BIN/createdb" -h 127.0.0.1 -p 5432 -U ubuntu stac
```

### 5. Install the pgstac schema

`pypgstac migrate` creates the `pgstac` schema, the partitioned
`items`/`collections` tables, the search functions, and the
`postgis` / `btree_gist` / `unaccent` extensions. Do not create those by hand.

```bash
python -m venv venv
venv/bin/pip install -r requirements-pgstac.txt

export PGHOST=127.0.0.1 PGPORT=5432 PGUSER=ubuntu PGDATABASE=stac
venv/bin/pypgstac migrate
```

Verify:

```bash
"$BIN/psql" -d stac -Atc "select version, datetime from pgstac.migrations;"
# 0.9.11|2026-07-14 10:41:31+00
```

### 6. Roles

`pypgstac migrate` creates `pgstac_admin`, `pgstac_ingest` and `pgstac_read`.
Add the login roles on top:

```sql
GRANT pgstac_admin TO ubuntu;

CREATE ROLE titiler LOGIN;
GRANT pgstac_read TO titiler;
```

`titiler` is read-only and is what `launch_titiler.sh` connects as:
`DATABASE_URL=postgresql://titiler@127.0.0.1:5432/stac`.

### 7. Register queryables

**Required.** Without this step `sortby: eo:cloud_cover` is silently ignored --
pgstac falls back to sorting the raw JSON value as *text*, so `"9.1"` sorts
after `"80.4"` and the cloudiest scenes win. The `to_float` wrapper is what
makes it a numeric sort.

`pgstac.queryables` has no unique index on `name` (uniqueness of
`(name, collection_ids)` is enforced by a constraint trigger), so `ON CONFLICT`
does not work here -- delete first, then insert:

```sql
DELETE FROM pgstac.queryables WHERE name = 'eo:cloud_cover';

INSERT INTO pgstac.queryables (name, definition, property_wrapper)
VALUES ('eo:cloud_cover',
        '{"type":"number","title":"Cloud Cover",
          "description":"Percent of pixels obscured by cloud"}'::jsonb,
        'to_float');
```

`collection_ids` is left NULL so the queryable applies to every collection, and
`property_index_type` is left NULL -- no per-partition index is created.

Expected end state (`id`, `datetime` and `geometry` come with pgstac):

```
datetime       | string |
eo:cloud_cover | number | to_float
geometry       |        |
id             |        |
```

### 8. Load the collections

The collection definitions in `collections/` are committed here. Load them,
then build and load the items:

```bash
for f in collections/*.json; do venv/bin/pypgstac load collections "$f" --method upsert; done
```

Items are **not** committed -- ~78 MB of NDJSON that is fully derivable from the
imagery on disk. Regenerate per year with the pipeline in
`image_pipeline/image_conversion_v2/stac/cog_stac_db/`:

| collection | build | load |
|---|---|---|
| `sentinel-2-l2a-rgb-cog-v2-<year>` | `build_cog_stac_v2.py --year <year>` | `load_cog_stac_v2.sh <year>` |
| `sentinel-2-l2a-jp2-de-<year>` | `build_jp2_stac_de.py --year <year>` | `load_jp2_stac_de.sh <year>` |

`run_remaining_years.sh` chains convert -> build -> load for a list of years
inside tmux.

## Collections

`collections/` holds the STAC collection definitions currently in the database.

| prefix | years | assets | pixels | CRS |
|---|---|---|---|---|
| `sentinel-2-l2a-rgb-cog-v2-` | 2018-2024 | `visual` (3-band RGB) | uint8, stretched 0-3000 -> 0-255 | EPSG:3857 |
| `sentinel-2-l2a-jp2-de-` | 2018-2024 | `B01`..`B12` | uint16 reflectance | native UTM |

The COG collections are for display only -- the pixels are contrast-stretched,
not reflectance. The `jp2-de` collections are the analysis-grade source and are
what the `/sentinel` bbox service reads (106 German MGRS tiles).

Both carry valid-data **polygon** footprints, not tile rectangles, so
`skipcovered` and bbox crops work correctly at scene edges.


