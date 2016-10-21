"""
Module with classes and methods to perform implicit regional modelling based on
the potential field method.
Tested on Ubuntu 14

Created on 10/10 /2016

@author: Miguel de la Varga
"""

import theano
import theano.tensor as T
import numpy as np
import matplotlib.pyplot as plt
from Visualization import GeoPlot


class Interpolator(GeoPlot):
    """
    Class which contain all needed methods to perform potential field implicit modelling
    """
    def __init__(self, range_var = 6, c_o = -0.58888888, nugget_effect = 0.3):
        """
        Basic interpolator parameters. Also here it is possible to change some flags of theano
        :param range: Range of the variogram, it is recommended the distance of the longest diagonal
        :param c_o: Sill of the variogram
        """
        theano.config.optimizer = "fast_run"
        theano.config.exception_verbosity = 'low'
        theano.config.compute_test_value = 'ignore'

        self.a = theano.shared(range_var, "range")
        self.c_o = theano.shared(c_o, "covariance at 0")
        self.nugget_effect_grad = theano.shared(nugget_effect, "nugget effect of the grade")

    def create_regular_grid_2D(self):
        """
        Method to create a 2D regular grid where we interpolate
        :return: 2D regular grid for the resoulution nx, ny
        """
        try:
            g = np.meshgrid(
                np.linspace(self.xmin,self.xmax,self.nx, dtype="float32"),
                np.linspace(self.ymin,self.ymax,self.ny, dtype="float32"),
            )
            self.grid = np.vstack(map(np.ravel,g)).T.astype("float32")
        except AttributeError:
            print("Extent or resolution not provided. Use set_extent and/or set_resolutions first")

    def create_regular_grid_3D(self):
        """
        Method to create a 3D regurlar grid where is interpolated
        :return: 3D regurlar grid for the resolution nx,ny
        """
        try:
            g = np.meshgrid(
                np.linspace(self.xmin, self.xmax, self.nx, dtype="float32"),
                np.linspace(self.ymin, self.ymax, self.ny, dtype="float32"),
                np.linspace(self.zmin, self.zmax, self.nz, dtype="float32"), indexing="ij"
            )

            self.grid = np.vstack(map(np.ravel, g)).T.astype("float32")
            self._universal_matrix = np.vstack((
                self.grid.T,
                (self.grid ** 2).T,
                self.grid[:, 0] * self.grid[:, 1],
                self.grid[:, 0] * self.grid[:, 2],
                self.grid[:, 1] * self.grid[:, 2]))
        except AttributeError:
             raise AttributeError("Extent or resolution not provided. Use set_extent and/or set_resolutions first")

    def theano_compilation_3D(self):
        """
        Function that generates the symbolic code to perform the interpolation
        :return: Array containing the potential field (maybe it returs all the pieces too I have to evaluate how
        this influences performance)
        """

        # Creation of symbolic variables
        dips_position = T.matrix("Position of the dips")
        dip_angles = T.vector("Angle of every dip")
        azimuth = T.vector("Azimuth")
        polarity = T.vector("Polarity")
        ref_layer_points = T.matrix("Reference points for every layer")
        rest_layer_points = T.matrix("Rest of the points of the layers")
        grid_val = theano.shared(self.grid, "Positions of the points to interpolate")
        universal_matrix = theano.shared(self._universal_matrix, "universal matrix")

        # Init values
        n_dimensions = 3
        grade_universal = 9

        # Calculating the dimensions of the
        length_of_CG = dips_position.shape[0] * n_dimensions
        length_of_CGI = rest_layer_points.shape[0]
        length_of_U_I = grade_universal
        length_of_C = length_of_CG + length_of_CGI# + length_of_U_I

        # ==========================================
        # Calculation of the covariance Matrix
        #===========================================
        # Auxiliary tile for dips and transformation to float 64 of variables in order to calculate precise euclidian
        # distances
        _aux_dips_pos = T.tile(dips_position, (n_dimensions, 1)).astype("float64")
        _aux_rest_layer_points = rest_layer_points.astype("float64")
        _aux_ref_layer_points = ref_layer_points.astype("float64")
        _aux_grid_val = grid_val.astype("float64")

        # Calculation of euclidian distances giving back float32
        SED_rest_rest = (T.sqrt(
            (_aux_rest_layer_points ** 2).sum(1).reshape((_aux_rest_layer_points.shape[0], 1)) +
            (_aux_rest_layer_points ** 2).sum(1).reshape((1, _aux_rest_layer_points.shape[0])) -
            2 * _aux_rest_layer_points.dot(_aux_rest_layer_points.T))).astype("float32")

        SED_ref_rest = (T.sqrt(
            (_aux_ref_layer_points ** 2).sum(1).reshape((_aux_ref_layer_points.shape[0], 1)) +
            (_aux_rest_layer_points ** 2).sum(1).reshape((1, _aux_rest_layer_points.shape[0])) -
            2 * _aux_ref_layer_points.dot(_aux_rest_layer_points.T))).astype("float32")

        SED_rest_ref = (T.sqrt(
            (_aux_rest_layer_points ** 2).sum(1).reshape((_aux_rest_layer_points.shape[0], 1)) +
            (_aux_ref_layer_points ** 2).sum(1).reshape((1, _aux_ref_layer_points.shape[0])) -
            2 * _aux_rest_layer_points.dot(_aux_ref_layer_points.T))).astype("float32")

        SED_ref_ref = (T.sqrt(
            (_aux_ref_layer_points ** 2).sum(1).reshape((_aux_ref_layer_points.shape[0], 1)) +
            (_aux_ref_layer_points ** 2).sum(1).reshape((1, _aux_ref_layer_points.shape[0])) -
            2 * _aux_ref_layer_points.dot(_aux_ref_layer_points.T))).astype("float32")

        SED_dips_dips = (T.sqrt(
            (_aux_dips_pos ** 2).sum(1).reshape((_aux_dips_pos.shape[0], 1)) +
            (_aux_dips_pos ** 2).sum(1).reshape((1, _aux_dips_pos.shape[0])) -
            2 * _aux_dips_pos.dot(_aux_dips_pos.T))).astype("float32")

        SED_dips_rest = (T.sqrt(
            (_aux_dips_pos ** 2).sum(1).reshape((_aux_dips_pos.shape[0], 1)) +
            (_aux_rest_layer_points ** 2).sum(1).reshape((1, _aux_rest_layer_points.shape[0])) -
            2 * _aux_dips_pos.dot(_aux_rest_layer_points.T))).astype("float32")

        SED_dips_ref = (T.sqrt(
            (_aux_dips_pos ** 2).sum(1).reshape((_aux_dips_pos.shape[0], 1)) +
            (_aux_ref_layer_points ** 2).sum(1).reshape((1, _aux_ref_layer_points.shape[0])) -
            2 * _aux_dips_pos.dot(_aux_ref_layer_points.T))).astype("float32")

        # Calculating euclidian distances between the point to simulate and the avalible data
        SED_dips_SimPoint = (T.sqrt(
            (_aux_dips_pos ** 2).sum(1).reshape((_aux_dips_pos.shape[0], 1)) +
            (_aux_grid_val ** 2).sum(1).reshape((1, _aux_grid_val.shape[0])) -
            2 * _aux_dips_pos.dot(_aux_grid_val.T))).astype("float32")

        SED_rest_SimPoint = (T.sqrt(
            (_aux_rest_layer_points ** 2).sum(1).reshape((_aux_rest_layer_points.shape[0], 1)) +
            (_aux_grid_val ** 2).sum(1).reshape((1, _aux_grid_val.shape[0])) -
            2 * _aux_rest_layer_points.dot(_aux_grid_val.T))).astype("float32")

        SED_ref_SimPoint = (T.sqrt(
            (_aux_ref_layer_points ** 2).sum(1).reshape((_aux_ref_layer_points.shape[0], 1)) +
            (_aux_grid_val ** 2).sum(1).reshape((1, _aux_grid_val.shape[0])) -
            2 * _aux_ref_layer_points.dot(_aux_grid_val.T))).astype("float32")

        # Cartesian distances between dips positions
        h_u = T.vertical_stack(
            T.tile(dips_position[:, 0] - dips_position[:, 0].reshape((dips_position[:, 0].shape[0], 1)), n_dimensions),
            T.tile(dips_position[:, 1] - dips_position[:, 1].reshape((dips_position[:, 1].shape[0], 1)), n_dimensions),
            T.tile(dips_position[:, 2] - dips_position[:, 2].reshape((dips_position[:, 2].shape[0], 1)), n_dimensions))

        h_v = h_u.T

        # Cartesian distances between dips and interface points
        # Rest
        hu_rest = T.vertical_stack(
            (dips_position[:, 0] - rest_layer_points[:, 0].reshape((rest_layer_points[:, 0].shape[0], 1))).T,
            (dips_position[:, 1] - rest_layer_points[:, 1].reshape((rest_layer_points[:, 1].shape[0], 1))).T,
            (dips_position[:, 2] - rest_layer_points[:, 2].reshape((rest_layer_points[:, 2].shape[0], 1))).T
        )

        # Reference point
        hu_ref = T.vertical_stack(
            (dips_position[:, 0] - ref_layer_points[:, 0].reshape((ref_layer_points[:, 0].shape[0], 1))).T,
            (dips_position[:, 1] - ref_layer_points[:, 1].reshape((ref_layer_points[:, 1].shape[0], 1))).T,
            (dips_position[:, 2] - ref_layer_points[:, 2].reshape((ref_layer_points[:, 2].shape[0], 1))).T
        )

        # Perpendicularity matrix (Explain better what this term means). Boolean matrix to separate cross-covariance and
        # every gradient direction covariance
        perpendicularity_matrix = T.ones_like(SED_dips_dips)

        # Cross-covariances of x
        perpendicularity_matrix = T.set_subtensor(
            perpendicularity_matrix[0:dips_position.shape[0], 0:dips_position.shape[0]], 0)

        # Cross-covariances of y
        perpendicularity_matrix = T.set_subtensor(
            perpendicularity_matrix[dips_position.shape[0]:dips_position.shape[0] * 2,
            dips_position.shape[0]:dips_position.shape[0] * 2], 0)

        # Cross-covariances of y
        perpendicularity_matrix = T.set_subtensor(
            perpendicularity_matrix[dips_position.shape[0] * 2:dips_position.shape[0] * 3,
            dips_position.shape[0] * 2:dips_position.shape[0] * 3], 0)

        # ==========================
        # Creating covariance Matrix
        # ==========================
        # Covariance matrix for interfaces
        C_I = ((SED_rest_rest < self.a) * self.c_o_pot_field *              # Rest - Rest Covariances Matrix
               (1 - 7 * (SED_rest_rest / self.a) ** 2 +
                35 / 4 * (SED_rest_rest / self.a) ** 3 -
                7 / 2 * (SED_rest_rest / self.a) ** 5 +
                3 / 4 * (SED_rest_rest / self.a) ** 7) -
               ((SED_ref_rest < self.a) * self.c_o_pot_field *              # Reference - Rest
               (1 - 7 * (SED_ref_rest / self.a) ** 2 +
                35 / 4 * (SED_ref_rest / self.a) ** 3 -
                7 / 2 * (SED_ref_rest / self.a) ** 5 +
                3 / 4 * (SED_ref_rest / self.a) ** 7)) -
               ((SED_rest_ref < self.a) * self.c_o_pot_field *             # Rest - Reference
               (1 - 7 * (SED_rest_ref / self.a) ** 2 +
                35 / 4 * (SED_rest_ref / self.a) ** 3 -
                7 / 2 * (SED_rest_ref / self.a) ** 5 +
                3 / 4 * (SED_rest_ref / self.a) ** 7)) +
               ((SED_ref_ref < self.a) * self.c_o_pot_field *             # Reference - References
               (1 - 7 * (SED_ref_ref / self.a) ** 2 +
                35 / 4 * (SED_ref_ref / self.a) ** 3 -
                7 / 2 * (SED_ref_ref / self.a) ** 5 +
                3 / 4 * (SED_ref_ref / self.a) ** 7)))

        # Covariance matrix for gradients at every xyz direction and their cross-covariances
        C_G = T.switch(
            T.eq(SED_dips_dips, 0),  # This is the condition
            0,                       # If true it is equal to 0. This is how a direction affect another
            (                        # else
             (-h_u * h_v / SED_dips_dips ** 2) *
             ((1 / SED_dips_dips) *
              (SED_dips_dips < self.a) *    # first derivative
              (-7 * (self.a - SED_dips_dips) ** 3 * SED_dips_dips *
              (8 * self.a ** 2 + 9 * self.a * SED_dips_dips + 3 * SED_dips_dips ** 2) * self.c_o) /
              (4 * self.a ** 7) -
              (SED_dips_dips < self.a) *    # Second derivative
              (-7 * (4. * self.a ** 5. - 15. * self.a ** 4. * SED_dips_dips + 20. *(self.a ** 2) *
               (SED_dips_dips ** 3) - 9 * SED_dips_dips ** 5) * self.c_o) / (2 * self.a ** 7)) +
             (perpendicularity_matrix *
              (SED_dips_dips < self.a) *     # first derivative
              (-7 * (self.a - SED_dips_dips) ** 3 * SED_dips_dips *8 * self.a ** 2 + 9 * self.a *
               SED_dips_dips + 3 * SED_dips_dips ** 2) * self.c_o) / (4 * self.a ** 7)
            )
                    )

        # Setting nugget effect of the gradients
        C_G = T.fill_diagonal(C_G, self.nugget_effect_grad)


        # Cross-Covariance gradients-interfaces
        C_GI = (hu_rest / SED_dips_rest *
                (SED_dips_rest < self.a) *    # first derivative
                (-7 * (self.a - SED_dips_rest) ** 3 * SED_dips_rest *
                 (8 * self.a ** 2 + 9 * self.a * SED_dips_rest + 3 * SED_dips_rest ** 2) * self.c_o) / (4 * self.a ** 7) -
                hu_ref / SED_dips_ref *
                (SED_dips_ref < self.a) *     # first derivative
                (-7 * (self.a - SED_dips_ref) ** 3 * SED_dips_ref *
                 (8 * self.a ** 2 + 9 * self.a * SED_dips_ref + 3 * SED_dips_ref ** 2) * self.c_o) / (4 * self.a ** 7)
                ).T
        """
        # ==========================
        # Condition of universality 1 degree
        # Gradients

        n = dips_position.shape[0]
        U_G = T.zeros((n * n_dimensions, n_dimensions))
        # x
        U_G = T.set_subtensor(
            U_G[:n, 0], 1)
        # y
        U_G = T.set_subtensor(
            U_G[n:n * 2, 1], 1
        )
        # z
        U_G = T.set_subtensor(
            U_G[n * 2: n * 3, 2], 1
        )

        # Interface
               # Cartesian distances between reference points and rest

        hx = T.stack(
            (rest_layer_points[:, 0] - ref_layer_points[:, 0]),
            (rest_layer_points[:, 1] - ref_layer_points[:, 1]),
            (rest_layer_points[:, 2] - ref_layer_points[:, 2])
        ).T

        U_I = hx


        # ==========================
        # Condition of universality 2 degree
        # Gradients

        n = dips_position.shape[0]
        U_G = T.zeros((n * n_dimensions, 3 * n_dimensions))
        # x
        U_G = T.set_subtensor(
            U_G[:n, 0], 1)
        # y
        U_G = T.set_subtensor(
            U_G[n * 1:n * 2, 1], 1
        )
        # z
        U_G = T.set_subtensor(
            U_G[n * 2: n * 3, 2], 1
        )
        # x**2
        U_G = T.set_subtensor(
            U_G[:n, 3], 2 * dips_position[:,0]
        )
        # y**2
        U_G = T.set_subtensor(
            U_G[n * 1:n * 2, 4], 2 * dips_position[:, 1]
        )
        # z**2
        U_G = T.set_subtensor(
            U_G[n * 2: n * 3, 5], 2 * dips_position[:, 2]
        )
        # xy
        U_G = T.set_subtensor(
            U_G[:n, 6], dips_position[:, 1] # This is y
        )

        U_G = T.set_subtensor(
            U_G[n * 1:n * 2, 6], dips_position[:, 0]  # This is x
        )

        # xz
        U_G = T.set_subtensor(
            U_G[:n, 7], dips_position[:, 2]  # This is z
        )
        U_G = T.set_subtensor(
            U_G[n * 2: n * 3, 7], dips_position[:, 0]  # This is x
        )

        # yz

        U_G = T.set_subtensor(
            U_G[n * 1:n * 2, 8], dips_position[:, 2]  # This is z
        )


        U_G = T.set_subtensor(
            U_G[n * 2:n * 3, 8], dips_position[:, 1]  # This is y
        )

        # Interface

        # Cartesian distances between reference points and rest

        U_I = T.stack(
            (rest_layer_points[:, 0] - ref_layer_points[:, 0]),
            (rest_layer_points[:, 1] - ref_layer_points[:, 1]),
            (rest_layer_points[:, 2] - ref_layer_points[:, 2]),
            (rest_layer_points[:, 0]**2 - ref_layer_points[:, 0]**2),
            (rest_layer_points[:, 1]**2 - ref_layer_points[:, 1]**2),
            (rest_layer_points[:, 2]**2 - ref_layer_points[:, 2]**2),
            (rest_layer_points[:, 0]*rest_layer_points[:, 1] - ref_layer_points[:, 0]*ref_layer_points[:, 1]),
            (rest_layer_points[:, 0]*rest_layer_points[:, 2] - ref_layer_points[:, 0]*ref_layer_points[:, 2]),
            (rest_layer_points[:, 1]*rest_layer_points[:, 2] - ref_layer_points[:, 1]*ref_layer_points[:, 2]),
        ).T

        #U_I = hx

        """

        # =================================
        # Creation of the Covariance Matrix
        # =================================
        C_matrix = T.zeros((length_of_C, length_of_C))

        # First row of matrices
        C_matrix = T.set_subtensor(C_matrix[0:length_of_CG, 0:length_of_CG], - C_G)

        C_matrix = T.set_subtensor(
            C_matrix[0:length_of_CG, length_of_CG:length_of_CG + length_of_CGI], C_GI.T)

   #     C_matrix = T.set_subtensor(
   #         C_matrix[0:length_of_CG, -length_of_U_I:], U_G)

        # Second row of matrices
        C_matrix = T.set_subtensor(
            C_matrix[length_of_CG:length_of_CG + length_of_CGI, 0:length_of_CG], C_GI)
        C_matrix = T.set_subtensor(
            C_matrix[length_of_CG:length_of_CG + length_of_CGI, length_of_CG:length_of_CG + length_of_CGI], C_I)

   #     C_matrix = T.set_subtensor(
   #         C_matrix[length_of_CG:length_of_CG + length_of_CGI, -length_of_U_I:], U_I)

        # Third row of matrices
   #     C_matrix = T.set_subtensor(
   #         C_matrix[-length_of_U_I:, 0:length_of_CG], U_G.T)
   #     C_matrix = T.set_subtensor(
   #         C_matrix[-length_of_U_I:, length_of_CG:length_of_CG + length_of_CGI], U_I.T)

        # =====================
        # Creation of the gradients G vector
        # Calculation of the cartesian components of the dips assuming the unit module
        G_x = T.sin(T.deg2rad(dip_angles)) * T.sin(T.deg2rad(azimuth)) * polarity
        G_y = T.sin(T.deg2rad(dip_angles)) * T.cos(T.deg2rad(azimuth)) * polarity
        G_z = T.cos(T.deg2rad(dip_angles)) * polarity

        G = T.concatenate((G_x, G_y, G_z))

        # Creation of the Dual Kriging vector
        b = T.zeros_like(C_matrix[:, 0])
        b = T.set_subtensor(b[0:G.shape[0]], G)

        # Solving the kriging system
        DK_parameters = T.dot(T.nlinalg.matrix_inverse(C_matrix), b)

        # ==============
        # Interpolator
        # ==============
        # Cartesian distances between the point to simulate and the dips
        hu_SimPoint = T.vertical_stack(
            (dips_position[:, 0] - grid_val[:, 0].reshape((grid_val[:, 0].shape[0], 1))).T,
            (dips_position[:, 1] - grid_val[:, 1].reshape((grid_val[:, 1].shape[0], 1))).T,
            (dips_position[:, 2] - grid_val[:, 2].reshape((grid_val[:, 2].shape[0], 1))).T
        )

        weigths = T.tile(DK_parameters, (grid_val.shape[0], 1)).T

        sigma_0_grad = (
            T.sum(
             weigths[:length_of_CG, :] *
             hu_SimPoint / SED_dips_SimPoint *
             ((SED_dips_SimPoint < self.a) *         # first derivative
              (-7 * (self.a - SED_dips_SimPoint) ** 3 * SED_dips_SimPoint *
              (8 * self.a ** 2 + 9 * self.a * SED_dips_SimPoint + 3 * SED_dips_SimPoint ** 2) * 1) / (4 * self.a ** 7))
             , axis=0))

        sigma_0_interf = (T.sum(
            weigths[length_of_CG:length_of_CG + length_of_CGI, :] *
            ((SED_rest_SimPoint < self.a) * self.c_o *               # Covariance cubic to rest
             (1 - 7 * (SED_rest_SimPoint / self.a) ** 2 +
             35 / 4 * (SED_rest_SimPoint / self.a) ** 3 -
             7 / 2 * (SED_rest_SimPoint / self.a) ** 5 +
             3 / 4 * (SED_rest_SimPoint / self.a) ** 7) -
             (SED_ref_SimPoint < self.a) * self.c_o *                # Covariance cubic to ref
             (1 - 7 * (SED_ref_SimPoint / self.a) ** 2 +
             35 / 4 * (SED_ref_SimPoint / self.a) ** 3 -
             7 / 2 * (SED_ref_SimPoint / self.a) ** 5 +
             3 / 4 * (SED_ref_SimPoint / self.a) ** 7)
             ), axis=0))

        f_0 = (T.sum(
            weigths[-length_of_U_I:, :] * universal_matrix, axis=0))

        Z_x = (sigma_0_grad + sigma_0_interf) #+ f_0)


        p =  (SED_dips_rest < self.a)
        o = (SED_dips_rest < self.a)*(  # first derivative
                -7 * (self.a - SED_dips_rest) ** 3 * SED_dips_rest *
                (8 * self.a ** 2 + 9 * self.a * SED_dips_rest + 3 * SED_dips_rest ** 2) * 1) /(4 * self.a ** 7)
        i = (SED_dips_ref < self.a)+0.0000001
        z = ((  # first derivative
                -7 * (self.a - SED_dips_ref) ** 3 * SED_dips_ref *
                (8 * self.a ** 2 + 9 * self.a * SED_dips_ref + 3 * SED_dips_ref ** 2) * 1) /(4 * self.a ** 7))
        u = ((SED_dips_ref < self.a)+0.0000001) * ((  # first derivative
                -7 * (self.a - SED_dips_ref) ** 3 * SED_dips_ref *
                (8 * self.a ** 2 + 9 * self.a * SED_dips_ref + 3 * SED_dips_ref ** 2) * 1) /(4 * self.a ** 7))
        """
        """

        self.interpolate = theano.function(
            [dips_position, dip_angles, azimuth, polarity, rest_layer_points, ref_layer_points],
            [Z_x, weigths, C_matrix, G_x, G_y, G_z],
            on_unused_input="warn", profile=True)


    def theano_set_2D(self):

        dips_position = T.matrix("Position of the dips")
        dip_angles = T.vector("Angle of every dip")
        ref_layer_points = T.matrix("Reference points for every layer")
        rest_layer_points = T.matrix("Rest of the points of the layers")
        grid_val = theano.shared(self.grid, "Positions of the points to interpolate")

        # Init values

        n_dimensions = 2
        grade_universal = 2

        length_of_CG = dips_position.shape[0] * n_dimensions
        length_of_CGI = rest_layer_points.shape[0]
        length_of_U_I = grade_universal
        length_of_C = length_of_CG + length_of_CGI + length_of_U_I


        # ======
        # Intermediate steps for the calculation of the covariance function

        # Auxiliar tile for dips

        _aux_dips_pos = T.tile(dips_position, (n_dimensions,1))

        # Calculation of euclidian distances between the different elements

        SED_rest_rest = T.sqrt(
            (rest_layer_points ** 2).sum(1).reshape((rest_layer_points.shape[0], 1)) +
            (rest_layer_points ** 2).sum(1).reshape((1, rest_layer_points.shape[0])) -
            2 * rest_layer_points.dot(rest_layer_points.T))

        SED_ref_rest = T.sqrt(
            (ref_layer_points ** 2).sum(1).reshape((ref_layer_points.shape[0], 1)) +
            (rest_layer_points ** 2).sum(1).reshape((1, rest_layer_points.shape[0])) -
            2 * ref_layer_points.dot(rest_layer_points.T))


        SED_rest_ref = T.sqrt(
            (rest_layer_points ** 2).sum(1).reshape((rest_layer_points.shape[0], 1)) +
            (ref_layer_points ** 2).sum(1).reshape((1, ref_layer_points.shape[0])) -
            2 * rest_layer_points.dot(ref_layer_points.T))

        SED_ref_ref = T.sqrt(
            (ref_layer_points ** 2).sum(1).reshape((ref_layer_points.shape[0], 1)) +
            (ref_layer_points ** 2).sum(1).reshape((1, ref_layer_points.shape[0])) -
            2 * ref_layer_points.dot(ref_layer_points.T))

        SED_dips_dips = T.sqrt(
            (_aux_dips_pos ** 2).sum(1).reshape((_aux_dips_pos.shape[0], 1)) +
            (_aux_dips_pos ** 2).sum(1).reshape((1, _aux_dips_pos.shape[0])) -
            2 * _aux_dips_pos.dot(_aux_dips_pos.T))

        SED_dips_rest = T.sqrt(
            (_aux_dips_pos ** 2).sum(1).reshape((_aux_dips_pos.shape[0], 1)) +
            (rest_layer_points ** 2).sum(1).reshape((1, rest_layer_points.shape[0])) -
            2 * _aux_dips_pos.dot(rest_layer_points.T))

        SED_dips_ref = T.sqrt(
            (_aux_dips_pos ** 2).sum(1).reshape((_aux_dips_pos.shape[0], 1)) +
            (ref_layer_points ** 2).sum(1).reshape((1, ref_layer_points.shape[0])) -
            2 * _aux_dips_pos.dot(ref_layer_points.T))

        # Cartesian distances between dips positions

        h_u = T.vertical_stack(
            T.tile(dips_position[:, 0] - dips_position[:, 0].reshape((dips_position[:, 0].shape[0], 1)), 2),   #x
            T.tile(dips_position[:, 1] - dips_position[:, 1].reshape((dips_position[:, 1].shape[0], 1)), 2), ) #y
        # T.tile(self.dips[:,2] - self.dips[:,2].reshape((self.dips[:,2].shape[0],1)),3))          #z

        h_v = h_u.T

        # Cartesian distances between dips and interface points

        hu_rest = T.vertical_stack(
        (dips_position[:, 0] - rest_layer_points[:, 0].reshape((rest_layer_points[:, 0].shape[0], 1))).T,
        (dips_position[:, 1] - rest_layer_points[:, 1].reshape((rest_layer_points[:, 1].shape[0], 1))).T
        )

        hu_ref = T.vertical_stack(
        (dips_position[:, 0] - ref_layer_points[:, 0].reshape((ref_layer_points[:, 0].shape[0], 1))).T,
        (dips_position[:, 1] - ref_layer_points[:, 1].reshape((ref_layer_points[:, 1].shape[0], 1))).T)

        # Cartesian distances between reference points and rest

        hx = T.stack(
        (rest_layer_points[:, 0] - ref_layer_points[:, 0]),
        (rest_layer_points[:, 1] - ref_layer_points[:, 1])
        ).T

        # Perpendicularity matrix

        perpendicularity_matrix = T.ones_like(SED_dips_dips)
        # 1D
        perpendicularity_matrix = T.set_subtensor(
            perpendicularity_matrix[0:dips_position.shape[1], 0:dips_position.shape[1]], 0)

        # 2D
        perpendicularity_matrix = T.set_subtensor(
            perpendicularity_matrix[dips_position.shape[1]:dips_position.shape[1] * 2,
            dips_position.shape[1]:dips_position.shape[1] * 2], 0)

        # 3D
        #    perpendicularity_matrix = T.set_subtensor(
        #        perpendicularity_matrix[self.dips.shape[1]*2:self.dips.shape[1]*3,
        #       self.dips.shape[1]*2:self.dips.shape[1] * 3 ], 1)

        # ==================
        # Covariance matrix for interfaces

        C_I = (
            (SED_rest_rest < self.a) * (1 - 7 * (SED_rest_rest / self.a) ** 2 +
            35 / 4 * (SED_rest_rest / self.a) ** 3 -
            7 / 2 * (SED_rest_rest / self.a) ** 5 +
            3 / 4 * (SED_rest_rest / self.a) ** 7) -
            (SED_ref_rest < self.a) * (1 - 7 * (SED_ref_rest / self.a) ** 2 +
            35 / 4 * (SED_ref_rest / self.a) ** 3 -
            7 / 2 * (SED_ref_rest / self.a) ** 5 +
            3 / 4 * (SED_ref_rest / self.a) ** 7) -
            (SED_rest_ref < self.a) * (1 - 7 * (SED_rest_ref / self.a) ** 2 +
            35 / 4 * (SED_rest_ref / self.a) ** 3 -
            7 / 2 * (SED_rest_ref / self.a) ** 5 +
            3 / 4 * (SED_rest_ref / self.a) ** 7) +
            (SED_ref_ref < self.a) * (1 - 7 * (SED_ref_ref / self.a) ** 2 +
            35 / 4 * (SED_ref_ref / self.a) ** 3 -
            7 / 2 * (SED_ref_ref / self.a) ** 5 +
            3 / 4 * (SED_ref_ref / self.a) ** 7)
        )

        printme = ( perpendicularity_matrix *
                        (SED_dips_dips < self.a) * (                                 # first derivative
                         -7 * (self.a - SED_dips_dips) ** 3 * SED_dips_dips *
                         (8 * self.a ** 2 + 9 * self.a * SED_dips_dips + 3 * SED_dips_dips ** 2) * 1) /
                         (4 * self.a ** 7))
        # =============
        # Covariance matrix for gradients at every xyz direction

        C_G = T.switch(
                       T.eq(SED_dips_dips, 0), # This is the condition
                       0,                     # If true it is equal to 0. This is how a direction affect another
                       (                      # else
                        #self.c_o*
                         (-h_u*h_v/SED_dips_dips**2)* ((1/SED_dips_dips) *
                         (SED_dips_dips < self.a) * (                                # first derivative
                         -7 * (self.a - SED_dips_dips) ** 3 * SED_dips_dips *
                         (8 * self.a ** 2 + 9 * self.a * SED_dips_dips + 3 * SED_dips_dips ** 2) * 1) /
                         (4 * self.a ** 7) -
                         (SED_dips_dips < self.a) * (                                # Second derivative
                         -7 * (4. * self.a ** 5. - 15. * self.a ** 4. * SED_dips_dips + 20. *
                         (self.a ** 2) * (SED_dips_dips ** 3) - 9 * SED_dips_dips ** 5) * 1) /
                         (2 * self.a ** 7)) +
                        # self.c_o *
                         perpendicularity_matrix *
                        (SED_dips_dips < self.a) * (                                 # first derivative
                         -7 * (self.a - SED_dips_dips) ** 3 * SED_dips_dips *
                         (8 * self.a ** 2 + 9 * self.a * SED_dips_dips + 3 * SED_dips_dips ** 2) * 1) /
                         (4 * self.a ** 7)
                        )
                       )
        C_G = T.fill_diagonal(C_G, self.c_o) # This sets the variance of the dips

        # ============
        # Cross-Covariance gradients-interfaces

        C_GI =(
            hu_rest / SED_dips_rest *
            (SED_dips_rest < self.a) * (       # first derivative
            -7 * (self.a - SED_dips_rest) ** 3 * SED_dips_rest *
            (8 * self.a ** 2 + 9 * self.a * SED_dips_rest + 3 * SED_dips_rest ** 2) * 1) /
            (4 * self.a ** 7) -
            hu_ref / SED_dips_ref *
            (SED_dips_ref < self.a) * (  # first derivative
            -7 * (self.a - SED_dips_ref) ** 3 * SED_dips_ref *
            (8 * self.a ** 2 + 9 * self.a * SED_dips_ref + 3 * SED_dips_ref ** 2) * 1) /
            (4 * self.a ** 7)
        ).T

        # ==========================
        # Condition of universality
        # Gradients

        n = dips_position.shape[0]
        U_G = T.zeros((n*2,2))
        U_G = T.set_subtensor(
            U_G[:n,0], 1)
        U_G = T.set_subtensor(
            U_G[n:,1],1
        )

        # Interface
        U_I = hx


        # ===================
        # Creation of the Covariance Matrix



        C_matrix = T.zeros((length_of_C, length_of_C))

        # First row of matrices
        C_matrix = T.set_subtensor(C_matrix[0:length_of_CG , 0:length_of_CG], -C_G)

        C_matrix = T.set_subtensor(
            C_matrix[0:length_of_CG , length_of_CG:length_of_CG  + length_of_CGI], C_GI.T)

        C_matrix = T.set_subtensor(
            C_matrix[0:length_of_CG, -length_of_U_I:], U_G)

        # Second row of matrices
        C_matrix = T.set_subtensor(
            C_matrix[length_of_CG:length_of_CG + length_of_CGI, 0:length_of_CG] ,C_GI)
        C_matrix = T.set_subtensor(
            C_matrix[length_of_CG:length_of_CG + length_of_CGI, length_of_CG:length_of_CG + length_of_CGI] ,C_I)

        C_matrix = T.set_subtensor(
            C_matrix[length_of_CG:length_of_CG + length_of_CGI, -length_of_U_I:], U_I)


        # Third row of matrices
        C_matrix = T.set_subtensor(
            C_matrix[-length_of_U_I:, 0:length_of_CG], U_G.T)
        C_matrix = T.set_subtensor(
            C_matrix[-length_of_U_I:, length_of_CG:length_of_CG+length_of_CGI] ,U_I.T)

        # =====================
        # Creation of the gradients G vector
        # Calculation of the cartesian components of the dips assuming the unit module:

        arrow_point_positions_x =  T.cos(T.deg2rad(dip_angles))
        arrow_point_positions_y =  T.sin(T.deg2rad(dip_angles))
        arrow_point_position = T.concatenate((arrow_point_positions_x, arrow_point_positions_y))

        G = arrow_point_position

        # ================
        # Creation of the kriging vector
        b = T.zeros_like(C_matrix[:, 0])
        b = T.set_subtensor(b[0:G.shape[0]],G)



        # ===============
        # Solving the kriging system

        DK_parameters= T.dot(T.nlinalg.matrix_inverse(C_matrix),b)


        # ==============
        # Interpolator
        # ==============
        # Calculating euclidian distances between the point to simulate and the avalible data

        SED_dips_SimPoint = T.sqrt(
            (_aux_dips_pos ** 2).sum(1).reshape((_aux_dips_pos.shape[0], 1)) +
            (grid_val ** 2).sum(1).reshape((1, grid_val.shape[0])) -
            2 * _aux_dips_pos.dot(grid_val.T))

        SED_rest_SimPoint = T.sqrt(
            (rest_layer_points ** 2).sum(1).reshape((rest_layer_points.shape[0], 1)) +
            (grid_val ** 2).sum(1).reshape((1, grid_val.shape[0])) -
            2 * rest_layer_points.dot(grid_val.T))

        SED_ref_SimPoint = T.sqrt(
            (ref_layer_points ** 2).sum(1).reshape((ref_layer_points.shape[0], 1)) +
            (grid_val ** 2).sum(1).reshape((1, grid_val.shape[0])) -
            2 * ref_layer_points.dot(grid_val.T))

        # Cartesian distances between the point to simulate and the dips

        hu_SimPoint = T.vertical_stack(
        (dips_position[:, 0] - grid_val[:, 0].reshape((grid_val[:, 0].shape[0], 1))).T,
        (dips_position[:, 1] - grid_val[:, 1].reshape((grid_val[:, 1].shape[0], 1))).T
        )


        weigths = T.tile(DK_parameters, (grid_val.shape[0],1)).T




        sigma_0_grad = (T.sum(
            weigths[:length_of_CG, :] * hu_SimPoint/SED_dips_SimPoint
            * (
            (SED_dips_SimPoint < self.a) * (  # first derivative
                -7 * (self.a - SED_dips_SimPoint) ** 3 * SED_dips_SimPoint *
                (8 * self.a ** 2 + 9 * self.a * SED_dips_SimPoint + 3 * SED_dips_SimPoint ** 2) * 1) /
            (4 * self.a ** 7)
        ), axis = 0))


        sigma_0_interf = (T.sum(
            weigths[length_of_CG:length_of_CG+length_of_CGI, :]*    # Covariance cubic to rest
                ((SED_rest_SimPoint < self.a) * (1 - 7 * (SED_rest_SimPoint / self.a) ** 2 +
            35 / 4 * (SED_rest_SimPoint / self.a) ** 3 -
            7 / 2 * (SED_rest_SimPoint / self.a) ** 5 +
            3 / 4 * (SED_rest_SimPoint / self.a) ** 7) -          # Covariance cubic to ref
            (SED_ref_SimPoint < self.a) * (1 - 7 * (SED_ref_SimPoint / self.a) ** 2 +
            35 / 4 * (SED_ref_SimPoint / self.a) ** 3 -
            7 / 2 * (SED_ref_SimPoint / self.a) ** 5 +
            3 / 4 * (SED_ref_SimPoint / self.a) ** 7)
                 ), axis = 0))

        f_0 = grid_val.T
        f_0 = (T.sum(
          weigths[-length_of_U_I:,:]* grid_val.T, axis = 0))


        Z_x = sigma_0_grad + sigma_0_interf + f_0
        """
        """
        self.geoMigueller = theano.function([dips_position, dip_angles, rest_layer_points, ref_layer_points], [Z_x,
                                C_I,C_G,C_GI,C_matrix, b, weigths,
                            printme, perpendicularity_matrix], on_unused_input="warn", profile= True)

    def theano_set_3D_nugget(self):





        dips_position = T.matrix("Position of the dips")
        dip_angles = T.vector("Angle of every dip")
        azimuth = T.vector("Azimuth")
        polarity = T.vector("Polarity")
        ref_layer_points = T.matrix("Reference points for every layer")
        rest_layer_points = T.matrix("Rest of the points of the layers")
        grid_val = theano.shared(self.grid, "Positions of the points to interpolate")
        universal_matrix = theano.shared(self._universal_matrix, "universal matrix")
        a = T.scalar()
        g = T.scalar()
        c = T.scalar()
        d = T.scalar()
        e = T.scalar()
        f = T.scalar()
        # euclidean_distances = theano.shared(self.euclidean_distances, "list with all euclidean distances needed")

        #TODO: change all shared variables to self. in order to be able to change its value as well as check it. Othewise it will be always necesary to compile what makes no sense
        """
        SED_dips_dips = euclidean_distances[0]
        SED_dips_ref = euclidean_distances[1]
        SED_dips_rest = euclidean_distances[2]
        SED_dips_SimPoint = euclidean_distances[3]
        SED_ref_ref = euclidean_distances[4]
        SED_ref_rest = euclidean_distances[5]
        SED_ref_SimPoint = euclidean_distances[6]
        SED_rest_rest = euclidean_distances[7]
        SED_rest_ref = euclidean_distances[8]
        SED_rest_SimPoint = euclidean_distances[9]
        """

        # Init values

        n_dimensions = 3
        grade_universal = 9

        length_of_CG = dips_position.shape[0] * n_dimensions
        length_of_CGI = rest_layer_points.shape[0]
        length_of_U_I = grade_universal
        length_of_C = length_of_CG + length_of_CGI + length_of_U_I

        # ======
        # Intermediate steps for the calculation of the covariance function

        # Auxiliar tile for dips

        _aux_dips_pos = T.tile(dips_position, (n_dimensions, 1)).astype("float64")
        _aux_rest_layer_points = rest_layer_points.astype("float64")
        _aux_ref_layer_points = ref_layer_points.astype("float64")
        _aux_grid_val = grid_val.astype("float64")

        # Calculation of euclidian distances between the different elements


        SED_rest_rest = (T.sqrt(
            (_aux_rest_layer_points ** 2).sum(1).reshape((_aux_rest_layer_points.shape[0], 1)) +
            (_aux_rest_layer_points ** 2).sum(1).reshape((1, _aux_rest_layer_points.shape[0])) -
            2 * _aux_rest_layer_points.dot(_aux_rest_layer_points.T))).astype("float32")

        SED_ref_rest = (T.sqrt(
            (_aux_ref_layer_points ** 2).sum(1).reshape((_aux_ref_layer_points.shape[0], 1)) +
            (_aux_rest_layer_points ** 2).sum(1).reshape((1, _aux_rest_layer_points.shape[0])) -
            2 * _aux_ref_layer_points.dot(_aux_rest_layer_points.T))).astype("float32")

        SED_rest_ref = (T.sqrt(
            (_aux_rest_layer_points ** 2).sum(1).reshape((_aux_rest_layer_points.shape[0], 1)) +
            (_aux_ref_layer_points ** 2).sum(1).reshape((1, _aux_ref_layer_points.shape[0])) -
            2 * _aux_rest_layer_points.dot(_aux_ref_layer_points.T))).astype("float32")

        SED_ref_ref = (T.sqrt(
            (_aux_ref_layer_points ** 2).sum(1).reshape((_aux_ref_layer_points.shape[0], 1)) +
            (_aux_ref_layer_points ** 2).sum(1).reshape((1, _aux_ref_layer_points.shape[0])) -
            2 * _aux_ref_layer_points.dot(_aux_ref_layer_points.T))).astype("float32")

        SED_dips_dips = (T.sqrt(
            (_aux_dips_pos ** 2).sum(1).reshape((_aux_dips_pos.shape[0], 1)) +
            (_aux_dips_pos ** 2).sum(1).reshape((1, _aux_dips_pos.shape[0])) -
            2 * _aux_dips_pos.dot(_aux_dips_pos.T))).astype("float32")

        SED_dips_rest = (T.sqrt(
            (_aux_dips_pos ** 2).sum(1).reshape((_aux_dips_pos.shape[0], 1)) +
            (_aux_rest_layer_points ** 2).sum(1).reshape((1, _aux_rest_layer_points.shape[0])) -
            2 * _aux_dips_pos.dot(_aux_rest_layer_points.T))).astype("float32")

        SED_dips_ref = (T.sqrt(
            (_aux_dips_pos ** 2).sum(1).reshape((_aux_dips_pos.shape[0], 1)) +
            (_aux_ref_layer_points ** 2).sum(1).reshape((1, _aux_ref_layer_points.shape[0])) -
            2 * _aux_dips_pos.dot(_aux_ref_layer_points.T))).astype("float32")

        # Calculating euclidian distances between the point to simulate and the avalible data

        SED_dips_SimPoint = (T.sqrt(
            (_aux_dips_pos ** 2).sum(1).reshape((_aux_dips_pos.shape[0], 1)) +
            (_aux_grid_val ** 2).sum(1).reshape((1, _aux_grid_val.shape[0])) -
            2 * _aux_dips_pos.dot(_aux_grid_val.T))).astype("float32")

        SED_rest_SimPoint = (T.sqrt(
            (_aux_rest_layer_points ** 2).sum(1).reshape((_aux_rest_layer_points.shape[0], 1)) +
            (_aux_grid_val ** 2).sum(1).reshape((1, _aux_grid_val.shape[0])) -
            2 * _aux_rest_layer_points.dot(_aux_grid_val.T))).astype("float32")

        SED_ref_SimPoint = (T.sqrt(
            (_aux_ref_layer_points ** 2).sum(1).reshape((_aux_ref_layer_points.shape[0], 1)) +
            (_aux_grid_val ** 2).sum(1).reshape((1, _aux_grid_val.shape[0])) -
            2 * _aux_ref_layer_points.dot(_aux_grid_val.T))).astype("float32")

        # Back to float32
        #     ref_layer_points = ref_layer_points.astype("float32")
        #  rest_layer_points = rest_layer_points.astype("float32")

        # =========
        # Cartesian distances

        # Cartesian distances between dips positions

        h_u = T.vertical_stack(
            T.tile(dips_position[:, 0] - dips_position[:, 0].reshape((dips_position[:, 0].shape[0], 1)), n_dimensions),
            # x
            T.tile(dips_position[:, 1] - dips_position[:, 1].reshape((dips_position[:, 1].shape[0], 1)), n_dimensions),
            # y
            T.tile(dips_position[:, 2] - dips_position[:, 2].reshape((dips_position[:, 2].shape[0], 1)),
                   n_dimensions))  # z

        h_v = h_u.T

        # Cartesian distances between dips and interface points
        # Rest
        hu_rest = T.vertical_stack(
            (dips_position[:, 0] - rest_layer_points[:, 0].reshape((rest_layer_points[:, 0].shape[0], 1))).T,
            (dips_position[:, 1] - rest_layer_points[:, 1].reshape((rest_layer_points[:, 1].shape[0], 1))).T,
            (dips_position[:, 2] - rest_layer_points[:, 2].reshape((rest_layer_points[:, 2].shape[0], 1))).T
        )

        # Reference point
        hu_ref = T.vertical_stack(
            (dips_position[:, 0] - ref_layer_points[:, 0].reshape((ref_layer_points[:, 0].shape[0], 1))).T,
            (dips_position[:, 1] - ref_layer_points[:, 1].reshape((ref_layer_points[:, 1].shape[0], 1))).T,
            (dips_position[:, 2] - ref_layer_points[:, 2].reshape((ref_layer_points[:, 2].shape[0], 1))).T
        )

        # Perpendicularity matrix

        perpendicularity_matrix = T.ones_like(SED_dips_dips)
        # 1D
        perpendicularity_matrix = T.set_subtensor(
            perpendicularity_matrix[0:dips_position.shape[0], 0:dips_position.shape[0]], 0)

        # 2D
        perpendicularity_matrix = T.set_subtensor(
            perpendicularity_matrix[dips_position.shape[0]:dips_position.shape[0] * 2,
            dips_position.shape[0]:dips_position.shape[0] * 2], 0)

        # 3D
        perpendicularity_matrix = T.set_subtensor(
            perpendicularity_matrix[dips_position.shape[0] * 2:dips_position.shape[0] * 3,
            dips_position.shape[0] * 2:dips_position.shape[0] * 3], 0)

        # ==================
        # Covariance matrix for interfaces

        C_I = a * (
            (SED_rest_rest < self.a) * (1 - 7 * (SED_rest_rest / self.a) ** 2 +
                                        35 / 4 * (SED_rest_rest / self.a) ** 3 -
                                        7 / 2 * (SED_rest_rest / self.a) ** 5 +
                                        3 / 4 * (SED_rest_rest / self.a) ** 7) -
            (SED_ref_rest < self.a) * (1 - 7 * (SED_ref_rest / self.a) ** 2 +
                                       35 / 4 * (SED_ref_rest / self.a) ** 3 -
                                       7 / 2 * (SED_ref_rest / self.a) ** 5 +
                                       3 / 4 * (SED_ref_rest / self.a) ** 7) -
            (SED_rest_ref < self.a) * (1 - 7 * (SED_rest_ref / self.a) ** 2 +
                                       35 / 4 * (SED_rest_ref / self.a) ** 3 -
                                       7 / 2 * (SED_rest_ref / self.a) ** 5 +
                                       3 / 4 * (SED_rest_ref / self.a) ** 7) +
            (SED_ref_ref < self.a) * (1 - 7 * (SED_ref_ref / self.a) ** 2 +
                                      35 / 4 * (SED_ref_ref / self.a) ** 3 -
                                      7 / 2 * (SED_ref_ref / self.a) ** 5 +
                                      3 / 4 * (SED_ref_ref / self.a) ** 7)
        )


        # =============
        # Covariance matrix for gradients at every xyz direction

        C_G = T.switch(
            T.eq(SED_dips_dips, 0),  # This is the condition
            0,  # If true it is equal to 0. This is how a direction affect another
            (  # else
                # self.c_o*
                (-h_u * h_v / SED_dips_dips ** 2) *
                ((1 / SED_dips_dips) *
                 (SED_dips_dips < self.a) * (  # first derivative
                     -7 * (self.a - SED_dips_dips) ** 3 * SED_dips_dips *
                     (
                         8 * self.a ** 2 + 9 * self.a * SED_dips_dips + 3 * SED_dips_dips ** 2) * 1) /
                 (4 * self.a ** 7) -
                 (SED_dips_dips < self.a) * (  # Second derivative
                     -7 * (
                         4. * self.a ** 5. - 15. * self.a ** 4. * SED_dips_dips + 20. *
                         (self.a ** 2) * (
                             SED_dips_dips ** 3) - 9 * SED_dips_dips ** 5) * 1) /
                 (2 * self.a ** 7)) +
                # self.c_o *
                perpendicularity_matrix *
                (SED_dips_dips < self.a) * (  # first derivative
                    -7 * (self.a - SED_dips_dips) ** 3 * SED_dips_dips *
                    (8 * self.a ** 2 + 9 * self.a * SED_dips_dips + 3 * SED_dips_dips ** 2) * 1) /
                (4 * self.a ** 7)
            )
        )

        C_G = g * T.fill_diagonal(C_G, c)  # This sets the variance of the dips
        # ============
        # Cross-Covariance gradients-interfaces

        C_GI = d * (
            hu_rest / SED_dips_rest *
            (SED_dips_rest < self.a) * (  # first derivative
                -7 * (self.a - SED_dips_rest) ** 3 * SED_dips_rest *
                (8 * self.a ** 2 + 9 * self.a * SED_dips_rest + 3 * SED_dips_rest ** 2) * 1) /
            (4 * self.a ** 7) -
            hu_ref / SED_dips_ref *
            (SED_dips_ref < self.a) * (  # first derivative
                -7 * (self.a - SED_dips_ref) ** 3 * SED_dips_ref *
                (8 * self.a ** 2 + 9 * self.a * SED_dips_ref + 3 * SED_dips_ref ** 2) * 1) /
            (4 * self.a ** 7)
        ).T


        # ==========================
        # Condition of universality 2 degree
        # Gradients

        n = dips_position.shape[0]
        U_G = T.zeros((n * n_dimensions, 3 * n_dimensions))
        # x
        U_G = T.set_subtensor(
            U_G[:n, 0], 1)
        # y
        U_G = T.set_subtensor(
            U_G[n * 1:n * 2, 1], 1
        )
        # z
        U_G = T.set_subtensor(
            U_G[n * 2: n * 3, 2], 1
        )
        # x**2
        U_G = T.set_subtensor(
            U_G[:n, 3], 2 * dips_position[:, 0]
        )
        # y**2
        U_G = T.set_subtensor(
            U_G[n * 1:n * 2, 4], 2 * dips_position[:, 1]
        )
        # z**2
        U_G = T.set_subtensor(
            U_G[n * 2: n * 3, 5], 2 * dips_position[:, 2]
        )
        # xy
        U_G = T.set_subtensor(
            U_G[:n, 6], dips_position[:, 1]  # This is y
        )

        U_G = T.set_subtensor(
            U_G[n * 1:n * 2, 6], dips_position[:, 0]  # This is x
        )

        # xz
        U_G = T.set_subtensor(
            U_G[:n, 7], dips_position[:, 2]  # This is z
        )
        U_G = T.set_subtensor(
            U_G[n * 2: n * 3, 7], dips_position[:, 0]  # This is x
        )

        # yz

        U_G = T.set_subtensor(
            U_G[n * 1:n * 2, 8], dips_position[:, 2]  # This is z
        )

        U_G = T.set_subtensor(
            U_G[n * 2:n * 3, 8], dips_position[:, 1]  # This is y
        )

        # Interface

        # Cartesian distances between reference points and rest

        U_I = T.stack(
            (rest_layer_points[:, 0] - ref_layer_points[:, 0]),
            (rest_layer_points[:, 1] - ref_layer_points[:, 1]),
            (rest_layer_points[:, 2] - ref_layer_points[:, 2]),
            (rest_layer_points[:, 0] ** 2 - ref_layer_points[:, 0] ** 2),
            (rest_layer_points[:, 1] ** 2 - ref_layer_points[:, 1] ** 2),
            (rest_layer_points[:, 2] ** 2 - ref_layer_points[:, 2] ** 2),
            (rest_layer_points[:, 0] * rest_layer_points[:, 1] - ref_layer_points[:, 0] * ref_layer_points[:, 1]),
            (rest_layer_points[:, 0] * rest_layer_points[:, 2] - ref_layer_points[:, 0] * ref_layer_points[:, 2]),
            (rest_layer_points[:, 1] * rest_layer_points[:, 2] - ref_layer_points[:, 1] * ref_layer_points[:, 2]),
        ).T


        # ===================
        # Creation of the Covariance Matrix

        C_matrix = T.zeros((length_of_C, length_of_C))

        # First row of matrices
        C_matrix = T.set_subtensor(C_matrix[0:length_of_CG, 0:length_of_CG], -C_G)

        C_matrix = T.set_subtensor(
            C_matrix[0:length_of_CG, length_of_CG:length_of_CG + length_of_CGI], C_GI.T)

        C_matrix = T.set_subtensor(
            C_matrix[0:length_of_CG, -length_of_U_I:], U_G)

        # Second row of matrices
        C_matrix = T.set_subtensor(
            C_matrix[length_of_CG:length_of_CG + length_of_CGI, 0:length_of_CG], C_GI)
        C_matrix = T.set_subtensor(
            C_matrix[length_of_CG:length_of_CG + length_of_CGI, length_of_CG:length_of_CG + length_of_CGI], C_I)

        C_matrix = T.set_subtensor(
            C_matrix[length_of_CG:length_of_CG + length_of_CGI, -length_of_U_I:], U_I)

        # Third row of matrices
        C_matrix = T.set_subtensor(
            C_matrix[-length_of_U_I:, 0:length_of_CG], U_G.T)
        C_matrix = T.set_subtensor(
            C_matrix[-length_of_U_I:, length_of_CG:length_of_CG + length_of_CGI], U_I.T)

        # =====================
        # Creation of the gradients G vector
        # Calculation of the cartesian components of the dips assuming the unit module:

        # arrow_point_positions_x = T.cos(T.deg2rad(dip_angles))
        # arrow_point_positions_y = T.sin(T.deg2rad(dip_angles))
        # arrow_point_position = T.concatenate((arrow_point_positions_x, arrow_point_positions_y))

        G_x = T.sin(T.deg2rad(dip_angles)) * T.sin(T.deg2rad(azimuth)) * polarity
        G_y = T.sin(T.deg2rad(dip_angles)) * T.cos(T.deg2rad(azimuth)) * polarity
        G_z = T.cos(T.deg2rad(dip_angles)) * polarity

        self.G_x = G_x
        self.G_y = G_y
        self.G_z = G_z

        G = T.concatenate((G_x, G_y, G_z))

        # ================
        # Creation of the kriging vector
        b = T.zeros_like(C_matrix[:, 0])
        b = T.set_subtensor(b[0:G.shape[0]], G)

        # ===============
        # Solving the kriging system

        DK_parameters = T.dot(T.nlinalg.matrix_inverse(C_matrix), b)

        # ==============
        # Interpolator
        # ==============


        # Cartesian distances between the point to simulate and the dips

        hu_SimPoint = T.vertical_stack(
            (dips_position[:, 0] - grid_val[:, 0].reshape((grid_val[:, 0].shape[0], 1))).T,
            (dips_position[:, 1] - grid_val[:, 1].reshape((grid_val[:, 1].shape[0], 1))).T,
            (dips_position[:, 2] - grid_val[:, 2].reshape((grid_val[:, 2].shape[0], 1))).T
        )

        weigths = T.tile(DK_parameters, (grid_val.shape[0], 1)).T

        #TODO multiply weights as a dot operation and not tiling it!
        sigma_0_grad = (
            T.sum(
                weigths[:length_of_CG, :] * e * hu_SimPoint / SED_dips_SimPoint * (
                    (SED_dips_SimPoint < self.a) * (  # first derivative
                        -7 * (self.a - SED_dips_SimPoint) ** 3 * SED_dips_SimPoint *
                        (8 * self.a ** 2 + 9 * self.a * SED_dips_SimPoint + 3 * SED_dips_SimPoint ** 2) * 1) /
                    (4 * self.a ** 7)
                ), axis=0))

        sigma_0_interf = (T.sum(
            weigths[length_of_CG:length_of_CG + length_of_CGI, :] * f *  # Covariance cubic to rest
            ((SED_rest_SimPoint < self.a) * (1 - 7 * (SED_rest_SimPoint / self.a) ** 2 +
                                             35 / 4 * (SED_rest_SimPoint / self.a) ** 3 -
                                             7 / 2 * (SED_rest_SimPoint / self.a) ** 5 +
                                             3 / 4 * (SED_rest_SimPoint / self.a) ** 7) -  # Covariance cubic to ref
             (SED_ref_SimPoint < self.a) * (1 - 7 * (SED_ref_SimPoint / self.a) ** 2 +
                                            35 / 4 * (SED_ref_SimPoint / self.a) ** 3 -
                                            7 / 2 * (SED_ref_SimPoint / self.a) ** 5 +
                                            3 / 4 * (SED_ref_SimPoint / self.a) ** 7)
             ), axis=0))

        f_0 = (T.sum(
            weigths[-length_of_U_I:, :] * universal_matrix, axis=0))

        Z_x = (sigma_0_grad + sigma_0_interf + f_0)

        """
        """

        self.geoMigueller = theano.function(
            [dips_position, dip_angles, azimuth, polarity, rest_layer_points, ref_layer_points, a, g, c, d, e, f],
            [Z_x, DK_parameters, b,
             G_x, G_y, G_z],
            on_unused_input="warn", profile=True, allow_input_downcast=True)


    def theano_set_3D_nugget_degree0(self):
        dips_position = T.matrix("Position of the dips")
        dip_angles = T.vector("Angle of every dip")
        azimuth = T.vector("Azimuth")
        polarity = T.vector("Polarity")
        ref_layer_points = T.matrix("Reference points for every layer")
        rest_layer_points = T.matrix("Rest of the points of the layers")
        grid_val = theano.shared(self.grid, "Positions of the points to interpolate")
        universal_matrix = theano.shared(self._universal_matrix, "universal matrix")
        a = T.scalar()
        g = T.scalar()
        c = T.scalar()
        d = T.scalar()
        e = T.scalar("palier")
        f = T.scalar()
        # euclidean_distances = theano.shared(self.euclidean_distances, "list with all euclidean distances needed")

        # TODO: change all shared variables to self. in order to be able to change its value as well as check it. Othewise it will be always necesary to compile what makes no sense
        """
        SED_dips_dips = euclidean_distances[0]
        SED_dips_ref = euclidean_distances[1]
        SED_dips_rest = euclidean_distances[2]
        SED_dips_SimPoint = euclidean_distances[3]
        SED_ref_ref = euclidean_distances[4]
        SED_ref_rest = euclidean_distances[5]
        SED_ref_SimPoint = euclidean_distances[6]
        SED_rest_rest = euclidean_distances[7]
        SED_rest_ref = euclidean_distances[8]
        SED_rest_SimPoint = euclidean_distances[9]
        """

        # Init values

        n_dimensions = 3
        grade_universal = 9

        length_of_CG = dips_position.shape[0] * n_dimensions
        length_of_CGI = rest_layer_points.shape[0]
        length_of_U_I = grade_universal
        length_of_C = length_of_CG + length_of_CGI

        # ======
        # Intermediate steps for the calculation of the covariance function

        # Auxiliar tile for dips

        _aux_dips_pos = T.tile(dips_position, (n_dimensions, 1)).astype("float64")
        _aux_rest_layer_points = rest_layer_points.astype("float64")
        _aux_ref_layer_points = ref_layer_points.astype("float64")
        _aux_grid_val = grid_val.astype("float64")

        # Calculation of euclidian distances between the different elements


        SED_rest_rest = (T.sqrt(
            (_aux_rest_layer_points ** 2).sum(1).reshape((_aux_rest_layer_points.shape[0], 1)) +
            (_aux_rest_layer_points ** 2).sum(1).reshape((1, _aux_rest_layer_points.shape[0])) -
            2 * _aux_rest_layer_points.dot(_aux_rest_layer_points.T))).astype("float64")

        SED_ref_rest = (T.sqrt(
            (_aux_ref_layer_points ** 2).sum(1).reshape((_aux_ref_layer_points.shape[0], 1)) +
            (_aux_rest_layer_points ** 2).sum(1).reshape((1, _aux_rest_layer_points.shape[0])) -
            2 * _aux_ref_layer_points.dot(_aux_rest_layer_points.T))).astype("float64")

        SED_rest_ref = (T.sqrt(
            (_aux_rest_layer_points ** 2).sum(1).reshape((_aux_rest_layer_points.shape[0], 1)) +
            (_aux_ref_layer_points ** 2).sum(1).reshape((1, _aux_ref_layer_points.shape[0])) -
            2 * _aux_rest_layer_points.dot(_aux_ref_layer_points.T))).astype("float64")

        SED_ref_ref = (T.sqrt(
            (_aux_ref_layer_points ** 2).sum(1).reshape((_aux_ref_layer_points.shape[0], 1)) +
            (_aux_ref_layer_points ** 2).sum(1).reshape((1, _aux_ref_layer_points.shape[0])) -
            2 * _aux_ref_layer_points.dot(_aux_ref_layer_points.T))).astype("float64")

        SED_dips_dips = (T.sqrt(
            (_aux_dips_pos ** 2).sum(1).reshape((_aux_dips_pos.shape[0], 1)) +
            (_aux_dips_pos ** 2).sum(1).reshape((1, _aux_dips_pos.shape[0])) -
            2 * _aux_dips_pos.dot(_aux_dips_pos.T))).astype("float64")

        SED_dips_rest = (T.sqrt(
            (_aux_dips_pos ** 2).sum(1).reshape((_aux_dips_pos.shape[0], 1)) +
            (_aux_rest_layer_points ** 2).sum(1).reshape((1, _aux_rest_layer_points.shape[0])) -
            2 * _aux_dips_pos.dot(_aux_rest_layer_points.T))).astype("float64")

        SED_dips_ref = (T.sqrt(
            (_aux_dips_pos ** 2).sum(1).reshape((_aux_dips_pos.shape[0], 1)) +
            (_aux_ref_layer_points ** 2).sum(1).reshape((1, _aux_ref_layer_points.shape[0])) -
            2 * _aux_dips_pos.dot(_aux_ref_layer_points.T))).astype("float64")

        # Calculating euclidian distances between the point to simulate and the avalible data

        SED_dips_SimPoint = (T.sqrt(
            (_aux_dips_pos ** 2).sum(1).reshape((_aux_dips_pos.shape[0], 1)) +
            (_aux_grid_val ** 2).sum(1).reshape((1, _aux_grid_val.shape[0])) -
            2 * _aux_dips_pos.dot(_aux_grid_val.T))).astype("float64")

        SED_rest_SimPoint = (T.sqrt(
            (_aux_rest_layer_points ** 2).sum(1).reshape((_aux_rest_layer_points.shape[0], 1)) +
            (_aux_grid_val ** 2).sum(1).reshape((1, _aux_grid_val.shape[0])) -
            2 * _aux_rest_layer_points.dot(_aux_grid_val.T))).astype("float64")

        SED_ref_SimPoint = (T.sqrt(
            (_aux_ref_layer_points ** 2).sum(1).reshape((_aux_ref_layer_points.shape[0], 1)) +
            (_aux_grid_val ** 2).sum(1).reshape((1, _aux_grid_val.shape[0])) -
            2 * _aux_ref_layer_points.dot(_aux_grid_val.T))).astype("float64")

        # Back to float64
        #     ref_layer_points = ref_layer_points.astype("float64")
        #  rest_layer_points = rest_layer_points.astype("float64")

        # =========
        # Cartesian distances

        # Cartesian distances between dips positions

        h_u = T.vertical_stack(
            T.tile(dips_position[:, 0] - dips_position[:, 0].reshape((dips_position[:, 0].shape[0], 1)), n_dimensions),
            # x
            T.tile(dips_position[:, 1] - dips_position[:, 1].reshape((dips_position[:, 1].shape[0], 1)), n_dimensions),
            # y
            T.tile(dips_position[:, 2] - dips_position[:, 2].reshape((dips_position[:, 2].shape[0], 1)),
                   n_dimensions))  # z

        h_v = h_u.T

        # Cartesian distances between dips and interface points
        # Rest
        hu_rest = T.vertical_stack(
            (dips_position[:, 0] - rest_layer_points[:, 0].reshape((rest_layer_points[:, 0].shape[0], 1))).T,
            (dips_position[:, 1] - rest_layer_points[:, 1].reshape((rest_layer_points[:, 1].shape[0], 1))).T,
            (dips_position[:, 2] - rest_layer_points[:, 2].reshape((rest_layer_points[:, 2].shape[0], 1))).T
        )

        # Reference point
        hu_ref = T.vertical_stack(
            (dips_position[:, 0] - ref_layer_points[:, 0].reshape((ref_layer_points[:, 0].shape[0], 1))).T,
            (dips_position[:, 1] - ref_layer_points[:, 1].reshape((ref_layer_points[:, 1].shape[0], 1))).T,
            (dips_position[:, 2] - ref_layer_points[:, 2].reshape((ref_layer_points[:, 2].shape[0], 1))).T
        )

        # Perpendicularity matrix

        perpendicularity_matrix = T.zeros_like(SED_dips_dips)
        # 1D
        perpendicularity_matrix = T.set_subtensor(
            perpendicularity_matrix[0:dips_position.shape[0], 0:dips_position.shape[0]], 1)

        # 2D
        perpendicularity_matrix = T.set_subtensor(
            perpendicularity_matrix[dips_position.shape[0]:dips_position.shape[0] * 2,
            dips_position.shape[0]:dips_position.shape[0] * 2], 1)

        # 3D
        perpendicularity_matrix = T.set_subtensor(
            perpendicularity_matrix[dips_position.shape[0] * 2:dips_position.shape[0] * 3,
            dips_position.shape[0] * 2:dips_position.shape[0] * 3], 1)


        #if SED_rest_rest.shape[0] == 1:
      #  SED_rest_rest = T.tile(SED_rest_rest, (2,2))
      #  SED_ref_rest = T.tile(SED_ref_rest, (1,2))
      #  SED_rest_ref = T.tile(SED_rest_ref, (2,1))

        # ==================
        # Covariance matrix for interfaces

        C_I = a  *(
            (SED_rest_rest < self.a) * (1 - 7 * (SED_rest_rest / self.a) ** 2 +
                                        35 / 4 * (SED_rest_rest / self.a) ** 3 -
                                        7 / 2 * (SED_rest_rest / self.a) ** 5 +
                                        3 / 4 * (SED_rest_rest / self.a) ** 7) -
            (SED_ref_rest < self.a) * (1 - 7 * (SED_ref_rest / self.a) ** 2 +
                                       35 / 4 * (SED_ref_rest / self.a) ** 3 -
                                       7 / 2 * (SED_ref_rest / self.a) ** 5 +
                                       3 / 4 * (SED_ref_rest / self.a) ** 7) -
            (SED_rest_ref < self.a) * (1 - 7 * (SED_rest_ref / self.a) ** 2 +
                                       35 / 4 * (SED_rest_ref / self.a) ** 3 -
                                       7 / 2 * (SED_rest_ref / self.a) ** 5 +
                                       3 / 4 * (SED_rest_ref / self.a) ** 7) +
            (SED_ref_ref < self.a) * (1 - 7 * (SED_ref_ref / self.a) ** 2 +
                                      35 / 4 * (SED_ref_ref / self.a) ** 3 -
                                      7 / 2 * (SED_ref_ref / self.a) ** 5 +
                                      3 / 4 * (SED_ref_ref / self.a) ** 7)
        )


        i1 = (SED_rest_rest < self.a) * (1 - 7 * (SED_rest_rest / self.a) ** 2 +
                                        35 / 4 * (SED_rest_rest / self.a) ** 3 -
                                        7 / 2 * (SED_rest_rest / self.a) ** 5 +
                                        3 / 4 * (SED_rest_rest / self.a) ** 7)

        i2 = (SED_ref_rest < self.a) * (1 - 7 * (SED_ref_rest / self.a) ** 2 +
                                       35 / 4 * (SED_ref_rest / self.a) ** 3 -
                                       7 / 2 * (SED_ref_rest / self.a) ** 5 +
                                       3 / 4 * (SED_ref_rest / self.a) ** 7)

        i3 =  (SED_rest_ref < self.a) * (1 - 7 * (SED_rest_ref / self.a) ** 2 +
                                       35 / 4 * (SED_rest_ref / self.a) ** 3 -
                                       7 / 2 * (SED_rest_ref / self.a) ** 5 +
                                       3 / 4 * (SED_rest_ref / self.a) ** 7)

        i4 = (SED_ref_ref < self.a) * (1 - 7 * (SED_ref_ref / self.a) ** 2 +
                                      35 / 4 * (SED_ref_ref / self.a) ** 3 -
                                      7 / 2 * (SED_ref_ref / self.a) ** 5 +
                                      3 / 4 * (SED_ref_ref / self.a) ** 7)


        # =============
        # Covariance matrix for gradients at every xyz direction

        C_G = T.switch(
            T.eq(SED_dips_dips, 0),  # This is the condition
            0,  # If true it is equal to 0. This is how a direction affect another
            (  # else, following Chiles book
                (h_u * h_v / SED_dips_dips ** 2) *
                (((SED_dips_dips < self.a) *  # first derivative
                  (-f*((-14/self.a**2)+ 105/4*SED_dips_dips/self.a**3-
                 35/2*SED_dips_dips**3/self.a**5 + 21/4*SED_dips_dips**5/self.a**7))) +
                 (SED_dips_dips < self.a) *  # Second derivative
                f * 7*(9 * SED_dips_dips**5-20*self.a**2*SED_dips_dips**3+
                       15*self.a**4*SED_dips_dips-4*self.a**5)/(2*self.a**7)))
             - (perpendicularity_matrix *
                 (SED_dips_dips < self.a) *  # first derivative
                  f * ((-14 / self.a ** 2) + 105 / 4 * SED_dips_dips / self.a ** 3 -
                  35 / 2 * SED_dips_dips ** 3 / self.a ** 5 + 21 / 4 * SED_dips_dips ** 5 / self.a ** 7)))


        C_G = T.fill_diagonal(C_G,  (-g * (-14 / self.a ** 2))+d)  # This sets the variance of the dips
        # ============
        # Cross-Covariance gradients-interfaces

        C_GI = e * ((
            (hu_rest) *
            (SED_dips_rest < self.a) *  # first derivative
            -f * ((-14 / self.a ** 2) + 105 / 4 * SED_dips_rest / self.a ** 3 -
                 35 / 2 * SED_dips_rest ** 3 / self.a ** 5 + 21 / 4 * SED_dips_rest ** 5 / self.a ** 7)) -
            (hu_ref)  *
                (SED_dips_ref < self.a) *  # first derivative
                -f * ((-14 / self.a ** 2) + 105 / 4 * SED_dips_ref / self.a ** 3 -
                     35 / 2 * SED_dips_ref ** 3 / self.a ** 5 + 21 / 4 * SED_dips_ref ** 5 / self.a ** 7)
        ).T

        gi1 =   ((hu_rest) *
            (SED_dips_rest < self.a) *  # first derivative
            f * ((-14 / self.a ** 2) + 105 / 4 * SED_dips_rest / self.a ** 3 -
                 35 / 2 * SED_dips_rest ** 3 / self.a ** 5 + 21 / 4 * SED_dips_rest ** 5 / self.a ** 7))
        gi2 = ( (hu_ref)  *
                (SED_dips_ref < self.a) *  # first derivative
                f * ((-14 / self.a ** 2) + 105 / 4 * SED_dips_ref / self.a ** 3 -
                     35 / 2 * SED_dips_ref ** 3 / self.a ** 5 + 21 / 4 * SED_dips_ref ** 5 / self.a ** 7))

        # ===================
        # Creation of the Covariance Matrix

        C_matrix = T.zeros((length_of_C, length_of_C))

        # First row of matrices
        C_matrix = T.set_subtensor(C_matrix[0:length_of_CG, 0:length_of_CG], C_G)

        C_matrix = T.set_subtensor(
            C_matrix[0:length_of_CG, length_of_CG:length_of_CG + length_of_CGI], C_GI.T)


        # Second row of matrices
        C_matrix = T.set_subtensor(
            C_matrix[length_of_CG:length_of_CG + length_of_CGI, 0:length_of_CG], C_GI)
        C_matrix = T.set_subtensor(
            C_matrix[length_of_CG:length_of_CG + length_of_CGI, length_of_CG:length_of_CG + length_of_CGI], C_I)


        # =====================
        # Creation of the gradients G vector

        G_x = T.sin(T.deg2rad(dip_angles)) * T.sin(T.deg2rad(azimuth)) * polarity
        G_y = T.sin(T.deg2rad(dip_angles)) * T.cos(T.deg2rad(azimuth)) * polarity
        G_z = T.cos(T.deg2rad(dip_angles)) * polarity

        self.G_x = G_x
        self.G_y = G_y
        self.G_z = G_z

        G = T.concatenate((G_x, G_y, G_z))

        # ================
        # Creation of the kriging vector
        b = T.zeros_like(C_matrix[:, 0])
        b = T.set_subtensor(b[0:G.shape[0]], G)

        # ===============
        # Solving the kriging system

        DK_parameters = T.dot(T.nlinalg.matrix_inverse(C_matrix), b)

        # ==============
        # Interpolator
        # ==============


        # Cartesian distances between the point to simulate and the dips

        hu_SimPoint = T.vertical_stack(
            (dips_position[:, 0] - grid_val[:, 0].reshape((grid_val[:, 0].shape[0], 1))).T,
            (dips_position[:, 1] - grid_val[:, 1].reshape((grid_val[:, 1].shape[0], 1))).T,
            (dips_position[:, 2] - grid_val[:, 2].reshape((grid_val[:, 2].shape[0], 1))).T
        )

        weigths = T.tile(DK_parameters, (grid_val.shape[0], 1)).T

        # TODO multiply weights as a dot operation and not tiling it!
        sigma_0_grad = (
            T.sum(
                weigths[:length_of_CG, :] * e * hu_SimPoint / SED_dips_SimPoint * (
                    (SED_dips_SimPoint < self.a) * (  # first derivative
                        -7 * (self.a - SED_dips_SimPoint) ** 3 * SED_dips_SimPoint *
                        (8 * self.a ** 2 + 9 * self.a * SED_dips_SimPoint + 3 * SED_dips_SimPoint ** 2) * 1) /
                    (4 * self.a ** 7)
                ), axis=0))

        sigma_0_interf = (T.sum(
            weigths[length_of_CG:length_of_CG + length_of_CGI, :] * f*  # Covariance cubic to rest
            ((SED_rest_SimPoint < self.a) * (1 - 7 * (SED_rest_SimPoint / self.a) ** 2 +
                                             35 / 4 * (SED_rest_SimPoint / self.a) ** 3 -
                                             7 / 2 * (SED_rest_SimPoint / self.a) ** 5 +
                                             3 / 4 * (SED_rest_SimPoint / self.a) ** 7) -  # Covariance cubic to ref
             (SED_ref_SimPoint < self.a) * f * (1 - 7 * (SED_ref_SimPoint / self.a) ** 2 +
                                            35 / 4 * (SED_ref_SimPoint / self.a) ** 3 -
                                            7 / 2 * (SED_ref_SimPoint / self.a) ** 5 +
                                            3 / 4 * (SED_ref_SimPoint / self.a) ** 7)
             ), axis=0))


        Z_x = (sigma_0_grad + sigma_0_interf )
        """
        DK_parameters, C_matrix, SED_dips_rest,  hu_rest,
             hu_ref, i1,i2,i3,i4,
             gi1, gi2,
             C_G,
             G_x, G_y, G_z

        """


        self.geoMigueller = theano.function(
            [dips_position, dip_angles, azimuth, polarity, rest_layer_points, ref_layer_points, a, g, c, d, e, f],
            [Z_x, DK_parameters, C_matrix, SED_dips_rest,  hu_rest,
             hu_ref, i1,i2,i3,i4,
             gi1, gi2,
             C_G,
             G_x, G_y, G_z],
            on_unused_input="warn", profile=True, allow_input_downcast=True)

    def theano_set_3D_nugget_degree0_2(self):
        dips_position = T.matrix("Position of the dips")
        dip_angles = T.vector("Angle of every dip")
        azimuth = T.vector("Azimuth")
        polarity = T.vector("Polarity")
        ref_layer_points = T.matrix("Reference points for every layer")
        rest_layer_points = T.matrix("Rest of the points of the layers")
        grid_val = theano.shared(self.grid, "Positions of the points to interpolate")
        universal_matrix = theano.shared(self._universal_matrix, "universal matrix")
        a = T.scalar()
        g = T.scalar()
        c = T.scalar()
        d = T.scalar()
        e = T.scalar("palier")
        f = T.scalar()
        # euclidean_distances = theano.shared(self.euclidean_distances, "list with all euclidean distances needed")

        # TODO: change all shared variables to self. in order to be able to change its value as well as check it. Othewise it will be always necesary to compile what makes no sense
        """
        SED_dips_dips = euclidean_distances[0]
        SED_dips_ref = euclidean_distances[1]
        SED_dips_rest = euclidean_distances[2]
        SED_dips_SimPoint = euclidean_distances[3]
        SED_ref_ref = euclidean_distances[4]
        SED_ref_rest = euclidean_distances[5]
        SED_ref_SimPoint = euclidean_distances[6]
        SED_rest_rest = euclidean_distances[7]
        SED_rest_ref = euclidean_distances[8]
        SED_rest_SimPoint = euclidean_distances[9]
        """

        # Init values

        n_dimensions = 3
        grade_universal = 9

        length_of_CG = dips_position.shape[0] * n_dimensions
        length_of_CGI = rest_layer_points.shape[0]
        length_of_U_I = grade_universal
        length_of_C = length_of_CG + length_of_CGI

        # ======
        # Intermediate steps for the calculation of the covariance function

        # Auxiliar tile for dips

        _aux_dips_pos = T.tile(dips_position, (n_dimensions, 1)).astype("float64")
        _aux_rest_layer_points = rest_layer_points.astype("float64")
        _aux_ref_layer_points = ref_layer_points.astype("float64")
        _aux_grid_val = grid_val.astype("float64")

        # Calculation of euclidian distances between the different elements


        SED_rest_rest = (T.sqrt(
            (_aux_rest_layer_points ** 2).sum(1).reshape((_aux_rest_layer_points.shape[0], 1)) +
            (_aux_rest_layer_points ** 2).sum(1).reshape((1, _aux_rest_layer_points.shape[0])) -
            2 * _aux_rest_layer_points.dot(_aux_rest_layer_points.T))).astype("float32")

        SED_ref_rest = (T.sqrt(
            (_aux_ref_layer_points ** 2).sum(1).reshape((_aux_ref_layer_points.shape[0], 1)) +
            (_aux_rest_layer_points ** 2).sum(1).reshape((1, _aux_rest_layer_points.shape[0])) -
            2 * _aux_ref_layer_points.dot(_aux_rest_layer_points.T))).astype("float32")

        SED_rest_ref = (T.sqrt(
            (_aux_rest_layer_points ** 2).sum(1).reshape((_aux_rest_layer_points.shape[0], 1)) +
            (_aux_ref_layer_points ** 2).sum(1).reshape((1, _aux_ref_layer_points.shape[0])) -
            2 * _aux_rest_layer_points.dot(_aux_ref_layer_points.T))).astype("float32")

        SED_ref_ref = (T.sqrt(
            (_aux_ref_layer_points ** 2).sum(1).reshape((_aux_ref_layer_points.shape[0], 1)) +
            (_aux_ref_layer_points ** 2).sum(1).reshape((1, _aux_ref_layer_points.shape[0])) -
            2 * _aux_ref_layer_points.dot(_aux_ref_layer_points.T))).astype("float32")

        SED_dips_dips = (T.sqrt(
            (_aux_dips_pos ** 2).sum(1).reshape((_aux_dips_pos.shape[0], 1)) +
            (_aux_dips_pos ** 2).sum(1).reshape((1, _aux_dips_pos.shape[0])) -
            2 * _aux_dips_pos.dot(_aux_dips_pos.T))).astype("float32")

        SED_dips_rest = (T.sqrt(
            (_aux_dips_pos ** 2).sum(1).reshape((_aux_dips_pos.shape[0], 1)) +
            (_aux_rest_layer_points ** 2).sum(1).reshape((1, _aux_rest_layer_points.shape[0])) -
            2 * _aux_dips_pos.dot(_aux_rest_layer_points.T))).astype("float32")

        SED_dips_ref = (T.sqrt(
            (_aux_dips_pos ** 2).sum(1).reshape((_aux_dips_pos.shape[0], 1)) +
            (_aux_ref_layer_points ** 2).sum(1).reshape((1, _aux_ref_layer_points.shape[0])) -
            2 * _aux_dips_pos.dot(_aux_ref_layer_points.T))).astype("float32")

        # Calculating euclidian distances between the point to simulate and the avalible data

        SED_dips_SimPoint = (T.sqrt(
            (_aux_dips_pos ** 2).sum(1).reshape((_aux_dips_pos.shape[0], 1)) +
            (_aux_grid_val ** 2).sum(1).reshape((1, _aux_grid_val.shape[0])) -
            2 * _aux_dips_pos.dot(_aux_grid_val.T))).astype("float32")

        SED_rest_SimPoint = (T.sqrt(
            (_aux_rest_layer_points ** 2).sum(1).reshape((_aux_rest_layer_points.shape[0], 1)) +
            (_aux_grid_val ** 2).sum(1).reshape((1, _aux_grid_val.shape[0])) -
            2 * _aux_rest_layer_points.dot(_aux_grid_val.T))).astype("float32")

        SED_ref_SimPoint = (T.sqrt(
            (_aux_ref_layer_points ** 2).sum(1).reshape((_aux_ref_layer_points.shape[0], 1)) +
            (_aux_grid_val ** 2).sum(1).reshape((1, _aux_grid_val.shape[0])) -
            2 * _aux_ref_layer_points.dot(_aux_grid_val.T))).astype("float32")

        # Back to float32
        #     ref_layer_points = ref_layer_points.astype("float32")
        #  rest_layer_points = rest_layer_points.astype("float32")

        # =========
        # Cartesian distances

        # Cartesian distances between dips positions

        h_u = T.vertical_stack(
            T.tile(dips_position[:, 0] - dips_position[:, 0].reshape((dips_position[:, 0].shape[0], 1)), n_dimensions),
            # x
            T.tile(dips_position[:, 1] - dips_position[:, 1].reshape((dips_position[:, 1].shape[0], 1)), n_dimensions),
            # y
            T.tile(dips_position[:, 2] - dips_position[:, 2].reshape((dips_position[:, 2].shape[0], 1)),
                   n_dimensions))  # z

        h_v = h_u.T

        # Cartesian distances between dips and interface points
        # Rest
        hu_rest = T.vertical_stack(
            (dips_position[:, 0] - rest_layer_points[:, 0].reshape((rest_layer_points[:, 0].shape[0], 1))).T,
            (dips_position[:, 1] - rest_layer_points[:, 1].reshape((rest_layer_points[:, 1].shape[0], 1))).T,
            (dips_position[:, 2] - rest_layer_points[:, 2].reshape((rest_layer_points[:, 2].shape[0], 1))).T
        )

        # Reference point
        hu_ref = T.vertical_stack(
            (dips_position[:, 0] - ref_layer_points[:, 0].reshape((ref_layer_points[:, 0].shape[0], 1))).T,
            (dips_position[:, 1] - ref_layer_points[:, 1].reshape((ref_layer_points[:, 1].shape[0], 1))).T,
            (dips_position[:, 2] - ref_layer_points[:, 2].reshape((ref_layer_points[:, 2].shape[0], 1))).T
        )

        # Perpendicularity matrix

        perpendicularity_matrix = T.ones_like(SED_dips_dips)
        # 1D
        perpendicularity_matrix = T.set_subtensor(
            perpendicularity_matrix[0:dips_position.shape[0], 0:dips_position.shape[0]], 0)

        # 2D
        perpendicularity_matrix = T.set_subtensor(
            perpendicularity_matrix[dips_position.shape[0]:dips_position.shape[0] * 2,
            dips_position.shape[0]:dips_position.shape[0] * 2], 0)

        # 3D
        perpendicularity_matrix = T.set_subtensor(
            perpendicularity_matrix[dips_position.shape[0] * 2:dips_position.shape[0] * 3,
            dips_position.shape[0] * 2:dips_position.shape[0] * 3], 0)

        # ==================
        # Covariance matrix for interfaces

        C_I = a + (
            (SED_rest_rest < self.a) * e* (1 - 7 * (SED_rest_rest / self.a) ** 2 +
                                        35 / 4 * (SED_rest_rest / self.a) ** 3 -
                                        7 / 2 * (SED_rest_rest / self.a) ** 5 +
                                        3 / 4 * (SED_rest_rest / self.a) ** 7) -
            (SED_ref_rest < self.a) * e *(1 - 7 * (SED_ref_rest / self.a) ** 2 +
                                       35 / 4 * (SED_ref_rest / self.a) ** 3 -
                                       7 / 2 * (SED_ref_rest / self.a) ** 5 +
                                       3 / 4 * (SED_ref_rest / self.a) ** 7) -
            (SED_rest_ref < self.a) * e* (1 - 7 * (SED_rest_ref / self.a) ** 2 +
                                       35 / 4 * (SED_rest_ref / self.a) ** 3 -
                                       7 / 2 * (SED_rest_ref / self.a) ** 5 +
                                       3 / 4 * (SED_rest_ref / self.a) ** 7) +
            (SED_ref_ref < self.a) * e * (1 - 7 * (SED_ref_ref / self.a) ** 2 +
                                      35 / 4 * (SED_ref_ref / self.a) ** 3 -
                                      7 / 2 * (SED_ref_ref / self.a) ** 5 +
                                      3 / 4 * (SED_ref_ref / self.a) ** 7)
        )

        # =============
        # Covariance matrix for gradients at every xyz direction

        C_G = T.switch(
            T.eq(SED_dips_dips, 0),  # This is the condition
            0,  # If true it is equal to 0. This is how a direction affect another
            (  # else
                # self.c_o*
                (-h_u * h_v / SED_dips_dips ** 2) *
                ((1 / SED_dips_dips) *
                 (SED_dips_dips < self.a) * (  # first derivative
                     -7 * (self.a - SED_dips_dips) ** 3 * SED_dips_dips *
                     (
                         8 * self.a ** 2 + 9 * self.a * SED_dips_dips + 3 * SED_dips_dips ** 2) * e) /
                 (4 * self.a ** 7) -
                 (SED_dips_dips < self.a) * (  # Second derivative
                     -7 * (
                         4. * self.a ** 5. - 15. * self.a ** 4. * SED_dips_dips + 20. *
                         (self.a ** 2) * (
                             SED_dips_dips ** 3) - 9 * SED_dips_dips ** 5) * e) /
                 (2 * self.a ** 7)) +
                # self.c_o *
                perpendicularity_matrix *
                (SED_dips_dips < self.a) * (  # first derivative
                    -7 * (self.a - SED_dips_dips) ** 3 * SED_dips_dips *
                    (8 * self.a ** 2 + 9 * self.a * SED_dips_dips + 3 * SED_dips_dips ** 2) * e) /
                (4 * self.a ** 7)
            )
        )

        C_G = g + T.fill_diagonal(C_G, c)  # This sets the variance of the dips
        # ============
        # Cross-Covariance gradients-interfaces

        C_GI = -(d + (
            hu_rest / SED_dips_rest *
            (SED_dips_rest < self.a) * (  # first derivative
                -7 * (self.a - SED_dips_rest) ** 3 * SED_dips_rest *
                (8 * self.a ** 2 + 9 * self.a * SED_dips_rest + 3 * SED_dips_rest ** 2) * e) /
            (4 * self.a ** 7) -
            hu_ref / SED_dips_ref *
            (SED_dips_ref < self.a) * (  # first derivative
                -7 * (self.a - SED_dips_ref) ** 3 * SED_dips_ref *
                (8 * self.a ** 2 + 9 * self.a * SED_dips_ref + 3 * SED_dips_ref ** 2) * e) /
            (4 * self.a ** 7)
        ).T)

        # ===================
        # Creation of the Covariance Matrix

        C_matrix = T.zeros((length_of_C, length_of_C))

        # First row of matrices
        C_matrix = T.set_subtensor(C_matrix[0:length_of_CG, 0:length_of_CG], -C_G)

        C_matrix = T.set_subtensor(
            C_matrix[0:length_of_CG, length_of_CG:length_of_CG + length_of_CGI], C_GI.T)

        # Second row of matrices
        C_matrix = T.set_subtensor(
            C_matrix[length_of_CG:length_of_CG + length_of_CGI, 0:length_of_CG], C_GI)
        C_matrix = T.set_subtensor(
            C_matrix[length_of_CG:length_of_CG + length_of_CGI, length_of_CG:length_of_CG + length_of_CGI], C_I)

        # =====================
        # Creation of the gradients G vector

        G_x = T.sin(T.deg2rad(dip_angles)) * T.sin(T.deg2rad(azimuth)) * polarity
        G_y = T.sin(T.deg2rad(dip_angles)) * T.cos(T.deg2rad(azimuth)) * polarity
        G_z = T.cos(T.deg2rad(dip_angles)) * polarity

        self.G_x = G_x
        self.G_y = G_y
        self.G_z = G_z

        G = T.concatenate((G_x, G_y, G_z))

        # ================
        # Creation of the kriging vector
        b = T.zeros_like(C_matrix[:, 0])
        b = T.set_subtensor(b[0:G.shape[0]], G)

        # ===============
        # Solving the kriging system

        DK_parameters = T.dot(T.nlinalg.matrix_inverse(C_matrix), b)

        # ==============
        # Interpolator
        # ==============


        # Cartesian distances between the point to simulate and the dips

        hu_SimPoint = T.vertical_stack(
            (dips_position[:, 0] - grid_val[:, 0].reshape((grid_val[:, 0].shape[0], 1))).T,
            (dips_position[:, 1] - grid_val[:, 1].reshape((grid_val[:, 1].shape[0], 1))).T,
            (dips_position[:, 2] - grid_val[:, 2].reshape((grid_val[:, 2].shape[0], 1))).T
        )

        weigths = T.tile(DK_parameters, (grid_val.shape[0], 1)).T

        # TODO multiply weights as a dot operation and not tiling it!
        sigma_0_grad = (
            T.sum(
                weigths[:length_of_CG, :] * e * hu_SimPoint / SED_dips_SimPoint * (
                    (SED_dips_SimPoint < self.a) * (  # first derivative
                        -7 * (self.a - SED_dips_SimPoint) ** 3 * SED_dips_SimPoint *
                        (8 * self.a ** 2 + 9 * self.a * SED_dips_SimPoint + 3 * SED_dips_SimPoint ** 2) * e) /
                    (4 * self.a ** 7)
                ), axis=0))

        sigma_0_interf = (T.sum(
            weigths[length_of_CG:length_of_CG + length_of_CGI, :] * f *  # Covariance cubic to rest
            ((SED_rest_SimPoint < self.a) * e *(1 - 7 * (SED_rest_SimPoint / self.a) ** 2 +
                                             35 / 4 * (SED_rest_SimPoint / self.a) ** 3 -
                                             7 / 2 * (SED_rest_SimPoint / self.a) ** 5 +
                                             3 / 4 * (SED_rest_SimPoint / self.a) ** 7) -  # Covariance cubic to ref
             (SED_ref_SimPoint < self.a) * e * (1 - 7 * (SED_ref_SimPoint / self.a) ** 2 +
                                            35 / 4 * (SED_ref_SimPoint / self.a) ** 3 -
                                            7 / 2 * (SED_ref_SimPoint / self.a) ** 5 +
                                            3 / 4 * (SED_ref_SimPoint / self.a) ** 7)
             ), axis=0))

        Z_x = (sigma_0_grad + sigma_0_interf)

        """
        """

        self.geoMigueller = theano.function(
            [dips_position, dip_angles, azimuth, polarity, rest_layer_points, ref_layer_points, a, g, c, d, e, f],
            [Z_x, DK_parameters, b,
             G_x, G_y, G_z],
            on_unused_input="warn", profile=True, allow_input_downcast=True)