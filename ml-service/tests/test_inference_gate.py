import unittest

from app.services.inference_gate import InferenceGate


class InferenceGateTests(unittest.TestCase):
    def test_rejects_when_capacity_is_full(self):
        gate = InferenceGate(capacity=1)

        self.assertTrue(gate.try_acquire())
        self.assertFalse(gate.try_acquire())

        self.assertEqual(
            gate.snapshot(),
            {
                "capacity": 1,
                "active": 1,
                "available": 0,
            },
        )

        gate.release()

        self.assertEqual(
            gate.snapshot(),
            {
                "capacity": 1,
                "active": 0,
                "available": 1,
            },
        )

    def test_slot_can_be_acquired_again_after_release(self):
        gate = InferenceGate(capacity=1)

        self.assertTrue(gate.try_acquire())
        gate.release()
        self.assertTrue(gate.try_acquire())
        gate.release()

    def test_invalid_capacity_is_rejected(self):
        with self.assertRaises(ValueError):
            InferenceGate(capacity=0)

    def test_extra_release_is_rejected(self):
        gate = InferenceGate(capacity=1)

        with self.assertRaises(RuntimeError):
            gate.release()


if __name__ == "__main__":
    unittest.main()