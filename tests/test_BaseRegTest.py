import os
import unittest
import numpy as np
from baseclasses import BaseRegTest
from baseclasses.testing import getTol
from baseclasses.testing.decorators import require_mpi
from baseclasses.utils import CaseInsensitiveDict

try:
    from mpi4py import MPI
except ImportError:
    MPI = None

baseDir = os.path.dirname(os.path.abspath(__file__))
# this is the dictionary of values to be added
root_vals = {
    "scalar": 1.0,
    "simple dictionary": {"a": 1.0},
    "nested dictionary": {"a": {"b": 1.0, "c": 2.0}},
}

# this is the dictionary for parallel tests
par_vals = {
    "par val": [0.5, 1.5],
    "par sum": 0.5 + 1.5,
    "par norm": np.sqrt(2.5),
}


class TestGetTol(unittest.TestCase):
    def test_tol(self):
        """
        Test that the getTol function is returning the appropriate values
        """
        x = 1e-1
        y = 1e-2
        c = 1e-3
        d = 1e-12
        r, a = getTol(atol=x, rtol=y)
        self.assertEqual(a, x)
        self.assertEqual(r, y)
        r, a = getTol(atol=c)
        self.assertEqual(a, c)
        self.assertEqual(r, d)
        r, a = getTol(rtol=c)
        self.assertEqual(a, d)
        self.assertEqual(r, c)
        r, a = getTol(tol=c)
        self.assertEqual(a, c)
        self.assertEqual(r, c)


class TestBaseRegTest(unittest.TestCase):
    N_PROCS = 2

    def setUp(self):
        if MPI is None:
            self.comm = None
            self.size = 1
            self.rank = 0
        else:
            self.comm = MPI.COMM_WORLD
            self.size = self.comm.size
            self.rank = self.comm.rank

    def regression_test_root(self, handler):
        """
        This function adds values for the root proc
        """
        for key, val in root_vals.items():
            if isinstance(val, dict):
                handler.root_add_dict(key, val)
            elif isinstance(val, (float, int)):
                handler.root_add_val(key, val)

        if handler.train:
            # check non-unique training value will throw ValueError
            # due to context manager, need to check for the generic Exception rather than specific ValueError
            with self.assertRaises(Exception):  # noqa: B017
                handler.root_add_val("scalar", 2.0)
            with self.assertRaises(Exception):  # noqa: B017
                handler.root_add_val("simple dictionary", {"c": -1})
        else:
            with self.assertRaises(Exception):  # noqa: B017
                handler.root_add_val("nonexisting dictionary", {"c": -1})

        # check if the compare argument works in training mode
        handler.root_add_val("scalar", 1.0, compare=True)
        with self.assertRaises(Exception):  # noqa: B017
            handler.root_add_val("scalar", 2.0, compare=True)

    def regression_test_par(self, handler):
        """
        This function adds values in parallel
        """
        val = self.rank + 0.5
        handler.par_add_val("par val", val)
        handler.par_add_sum("par sum", val)
        handler.par_add_norm("par norm", val)

    def test_train_then_test_root(self):
        """
        Test for adding values to the root, both in training and in testing
        Also tests read/write in the process
        """
        self.ref_file = os.path.join(baseDir, "test_root.ref")
        metadata = {"options": CaseInsensitiveDict({})}
        with BaseRegTest(self.ref_file, train=True) as handler:
            self.regression_test_root(handler)
            handler.add_metadata(metadata)
            # More added at later stage, like version
            metadata["version"] = "1.2.3"
            handler.add_metadata(metadata)
        test_vals = handler.readRef()
        # check the two values match
        self.assertEqual(test_vals, root_vals)
        self.assertEqual(handler.get_metadata(), metadata)

        # test train=False
        handler = BaseRegTest(self.ref_file, train=False)
        self.regression_test_root(handler)

    @require_mpi
    def test_train_then_test_par(self):
        """
        Test for adding values in parallel, both in training and in testing
        Also tests read/write in the process
        """
        self.ref_file = os.path.join(baseDir, "test_par.ref")
        with BaseRegTest(self.ref_file, train=True) as handler:
            self.regression_test_par(handler)
        test_vals = handler.readRef()
        self.assertEqual(test_vals, par_vals)
        with BaseRegTest(self.ref_file, train=False) as handler:
            self.regression_test_par(handler)

    def tearDown(self):
        if self.rank == 0 and hasattr(self, "ref_file"):
            os.remove(self.ref_file)
