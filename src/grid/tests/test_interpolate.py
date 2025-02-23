"""Interpolation tests file."""
from unittest import TestCase

from grid.atomic_grid import AtomicGrid
from grid.interpolate import (
    _generate_sph_paras,
    generate_real_sph_harms,
    generate_sph_harms,
    interpolate,
    spline_with_sph_harms,
)
from grid.lebedev import generate_lebedev_grid
from grid.onedgrid import HortonLinear
from grid.rtransform import IdentityRTransform

import numpy as np
from numpy.testing import assert_allclose, assert_almost_equal, assert_array_equal


class TestInterpolate(TestCase):
    """Interpolation test class."""

    def setUp(self):
        """Generate atomic grid for constant test call."""
        self.ang_grid = generate_lebedev_grid(degree=7)

    def test_generate_sph_parameters(self):
        """Test spherical harmonics parameter generator function."""
        for max_l in range(20):
            l, m = _generate_sph_paras(max_l)
            assert_array_equal(l, np.arange(max_l + 1))
            # first l elements of m
            assert_array_equal(m[: max_l + 1], l)
            # last l - 1 elements of me
            assert_array_equal(m[max_l + 1 :], np.arange(-max_l, 0))

    def test_generate_sph_harms(self):
        """Tets generated spherical harmonics values."""
        pts = self.ang_grid.points
        wts = self.ang_grid.weights
        r = np.linalg.norm(pts, axis=1)
        # polar
        phi = np.arccos(pts[:, 2] / r)
        # azimuthal
        theta = np.arctan2(pts[:, 1], pts[:, 0])
        # generate spherical harmonics
        sph_h = generate_sph_harms(3, theta, phi)  # l_max = 3
        assert sph_h.shape == (7, 4, 26)
        # test spherical harmonics integrated to 1 if the same index else 0.
        for _ in range(20):
            n = np.random.randint(0, 4, 2)
            m1 = np.random.randint(-n[0], n[0] + 1)
            m2 = np.random.randint(-n[1], n[1] + 1)
            re = sum(sph_h[m1, n[0]] * np.conjugate(sph_h[m2, n[1]]) * wts)
            if n[0] != n[1] or m1 != m2:
                print(n, m1, m2, re)
                assert_almost_equal(re, 0)
            else:
                print(n, m1, m2, re)
                assert_almost_equal(re, 1)

    def test_generate_real_sph_harms(self):
        """Test generated real spherical harmonics values."""
        pts = self.ang_grid.points
        wts = self.ang_grid.weights
        r = np.linalg.norm(pts, axis=1)
        # polar
        phi = np.arccos(pts[:, 2] / r)
        # azimuthal
        theta = np.arctan2(pts[:, 1], pts[:, 0])
        # generate spherical harmonics
        sph_h = generate_real_sph_harms(3, theta, phi)  # l_max = 3
        assert sph_h.shape == (7, 4, 26)
        for _ in range(20):
            n = np.random.randint(0, 4, 2)
            m1 = np.random.randint(-n[0], n[0] + 1)
            m2 = np.random.randint(-n[1], n[1] + 1)
            re = sum(sph_h[m1, n[0]] * sph_h[m2, n[1]] * wts)
            if n[0] != n[1] or m1 != m2:
                print(n, m1, m2, re)
                assert_almost_equal(re, 0)
            else:
                print(n, m1, m2, re)
                assert_almost_equal(re, 1)
            # no nan in the final result
            assert np.sum(np.isnan(re)) == 0

    def helper_func_power(self, points):
        """Compute function value for test interpolation."""
        return 2 * points[:, 0] ** 2 + 3 * points[:, 1] ** 2 + 4 * points[:, 2] ** 2

    def helper_func_power_deriv(self, points):
        """Compute function derivative for test derivation.

        Not fully understandd why this work, but gave the same result.
        """
        r = np.linalg.norm(points, axis=1)
        dxf = 4 * points[:, 0] * points[:, 0] / r
        dyf = 6 * points[:, 1] * points[:, 1] / r
        dzf = 8 * points[:, 2] * points[:, 2] / r
        return dxf + dyf + dzf

    def test_spline_with_sph_harms(self):
        """Test spline projection the same as spherical harmonics."""
        rad = IdentityRTransform().transform_grid(HortonLinear(10))
        rad._points += 1
        atgrid = AtomicGrid.special_init(rad, 1, scales=[], degs=[7])
        sph_coor = atgrid.convert_cart_to_sph()
        values = self.helper_func_power(atgrid.points)
        l_max = atgrid.l_max // 2
        r_sph = generate_real_sph_harms(l_max, sph_coor[:, 0], sph_coor[:, 1])
        result = spline_with_sph_harms(
            r_sph, values, atgrid.weights, atgrid.indices, rad.points
        )
        # generate ref
        # for shell in range(1, 11):
        for shell in range(1, 11):
            sh_grid = atgrid.get_shell_grid(shell - 1, r_sq=False)
            r = np.linalg.norm(sh_grid._points, axis=1)
            theta = np.arctan2(sh_grid._points[:, 1], sh_grid._points[:, 0])
            phi = np.arccos(sh_grid._points[:, 2] / r)
            r_sph = generate_real_sph_harms(l_max, theta, phi)
            r_sph_proj = np.sum(
                r_sph * self.helper_func_power(sh_grid.points) * sh_grid.weights,
                axis=-1,
            )
            assert_allclose(r_sph_proj, result(shell), atol=1e-10)

    def test_cubicspline_and_interp(self):
        """Test cubicspline interpolation values."""
        rad = IdentityRTransform().transform_grid(HortonLinear(10))
        rad._points += 1
        atgrid = AtomicGrid.special_init(rad, 1, scales=[], degs=[7])
        sph_coor = atgrid.convert_cart_to_sph()
        values = self.helper_func_power(atgrid.points)
        l_max = atgrid.l_max // 2
        r_sph = generate_real_sph_harms(l_max, sph_coor[:, 0], sph_coor[:, 1])
        result = spline_with_sph_harms(
            r_sph, values, atgrid.weights, atgrid.indices, rad.points
        )
        semi_sph_c = sph_coor[atgrid.indices[5] : atgrid.indices[6]]
        interp = interpolate(result, 6, semi_sph_c[:, 0], semi_sph_c[:, 1])
        # same result from points and interpolation
        assert_allclose(interp, values[atgrid.indices[5] : atgrid.indices[6]])

        # random multiple interpolation test
        for _ in range(100):
            indices = np.random.randint(1, 11, np.random.randint(1, 10))
            interp = interpolate(result, indices, semi_sph_c[:, 0], semi_sph_c[:, 1])
            for i, j in enumerate(indices):
                assert_allclose(
                    interp[i], values[atgrid.indices[j - 1] : atgrid.indices[j]]
                )

        # test random x, y, z
        xyz = np.random.rand(10, 3)
        xyz /= np.linalg.norm(xyz, axis=-1)[:, None]
        rad = np.random.normal() * np.random.randint(1, 11)
        xyz *= rad
        ref_value = self.helper_func_power(xyz)

        r = np.linalg.norm(xyz, axis=-1)
        theta = np.arctan2(xyz[:, 1], xyz[:, 0])
        phi = np.arccos(xyz[:, 2] / r)
        interp = interpolate(result, np.abs(rad), theta, phi)
        assert_allclose(interp, ref_value)

    def test_cubicspline_and_deriv(self):
        """Test spline for derivation."""
        rad = IdentityRTransform().transform_grid(HortonLinear(10))
        rad._points += 1
        atgrid = AtomicGrid.special_init(rad, 1, scales=[], degs=[7])
        sph_coor = atgrid.convert_cart_to_sph()
        values = self.helper_func_power(atgrid.points)
        l_max = atgrid.l_max // 2
        r_sph = generate_real_sph_harms(l_max, sph_coor[:, 0], sph_coor[:, 1])
        result = spline_with_sph_harms(
            r_sph, values, atgrid.weights, atgrid.indices, rad.points
        )
        semi_sph_c = sph_coor[atgrid.indices[5] : atgrid.indices[6]]
        interp = interpolate(result, 6, semi_sph_c[:, 0], semi_sph_c[:, 1], deriv=1)
        # same result from points and interpolation
        ref_deriv = self.helper_func_power_deriv(
            atgrid.points[atgrid.indices[5] : atgrid.indices[6]]
        )
        assert_allclose(interp, ref_deriv)

        # test random x, y, z with fd
        xyz = np.random.rand(1, 3)
        xyz /= np.linalg.norm(xyz, axis=-1)[:, None]
        rad = np.random.normal() * np.random.randint(1, 11)
        xyz *= rad
        ref_value = self.helper_func_power_deriv(xyz)

        r = np.linalg.norm(xyz, axis=-1)
        theta = np.arctan2(xyz[:, 1], xyz[:, 0])
        phi = np.arccos(xyz[:, 2] / r)
        interp = interpolate(result, np.abs(rad), theta, phi, deriv=1)
        assert_allclose(interp, ref_value)

        with self.assertRaises(ValueError):
            interp = interpolate(result, 6, semi_sph_c[:, 0], semi_sph_c[:, 1], deriv=4)
        with self.assertRaises(ValueError):
            interp = interpolate(
                result, 6, semi_sph_c[:, 0], semi_sph_c[:, 1], deriv=-1
            )
