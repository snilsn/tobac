"""Provide feature detection.

This module can work with any two-dimensional field.
To identify the features, contiguous regions above or 
below a threshold are determined and labelled individually.
To describe the specific location of the feature at a 
specific point in time, different spatial properties 
are used to describe the identified region. [2]_

References
----------
.. Heikenfeld, M., Marinescu, P. J., Christensen, M.,
   Watson-Parris, D., Senf, F., van den Heever, S. C.
   & Stier, P. (2019). tobac 1.2: towards a flexible 
   framework for tracking and analysis of clouds in 
   diverse datasets. Geoscientific Model Development,
   12(11), 4551-4570.
"""

import logging
import numpy as np
import pandas as pd
from . import utils as tb_utils
from tobac.utils import spectral_filtering
import warnings
from . import utils as tb_utils


def feature_position(
    hdim1_indices,
    hdim2_indices,
    vdim_indices=None,
    region_small=None,
    region_bbox=None,
    track_data=None,
    threshold_i=None,
    position_threshold="center",
    target=None,
    PBC_flag="none",
    x_min=0,
    x_max=0,
    y_min=0,
    y_max=0,
):
    """Determine feature position with regard to the horizontal
    dimensions in pixels from the identified region above
    threshold values

    Parameters
    ----------
    hdim1_indices : list
        indices of pixels in region along first horizontal
        dimension

    hdim2_indices : list
        indices of pixels in region along second horizontal
        dimension

    vdim_indices : list, optional
        List of indices of feature along optional vdim (typically ```z```)

    region_small : 2D or 3D array-like
        A true/false array containing True where the threshold
        is met and false where the threshold isn't met. This
        array should be the the size specified by region_bbox,
        and can be a subset of the overall input array
        (i.e., ```track_data```).

    region_bbox : list or tuple with length of 4 or 6
        The coordinates that region_small occupies within the total track_data
        array. This is in the order that the coordinates come from the
        ```get_label_props_in_dict``` function. For 2D data, this should be:
        (hdim1 start, hdim 2 start, hdim 1 end, hdim 2 end). For 3D data, this
        is: (vdim start, hdim1 start, hdim 2 start, vdim end, hdim 1 end, hdim 2 end).

    track_data : 2D or 3D array-like
        2D or 3D array containing the data

    threshold_i : float
        The threshold value that we are testing against

    position_threshold : {'center', 'extreme', 'weighted_diff', '
                          weighted abs'}
        How to select the single point position from our data.
        'center' picks the geometrical centre of the region,
        and is typically not recommended. 'extreme' picks the
        maximum or minimum value inside the region (max/min set by
         ```target```) 'weighted_diff' picks the centre of the
         region weighted by the distance from the threshold value
        'weighted_abs' picks the centre of the region weighted by
        the absolute values of the field

    target : {'maximum', 'minimum'}
        Used only when position_threshold is set to 'extreme',
        this sets whether it is looking for maxima or minima.

    PBC_flag : {'none', 'hdim_1', 'hdim_2', 'both'}
        Sets whether to use periodic boundaries, and if so in which directions.
        'none' means that we do not have periodic boundaries
        'hdim_1' means that we are periodic along hdim1
        'hdim_2' means that we are periodic along hdim2
        'both' means that we are periodic along both horizontal dimensions

    x_min : int
        Minimum real x coordinate (for PBCs)

    x_max: int
        Maximum real x coordinate (for PBCs)

    y_min : int
        Minimum real y coordinate (for PBCs)

    y_max : int
        Maximum real y coordinate (for PBCs)

    Returns
    -------
    float
            (if 3D) feature position along vertical dimension
    float
            feature position along 1st horizontal dimension
    float
            feature position along 2nd horizontal dimension
    """

    # First, if necessary, run PBC processing.
    # processing of PBC indices
    # checks to see if minimum and maximum values are present in dimensional array
    # then if true, adds max value to any indices past the halfway point of their respective dimension
    # are we 3D? if so, True.
    is_3D = False

    pbc_options = ["hdim_1", "hdim_2", "both"]

    hdim1_indices_2 = hdim1_indices
    hdim2_indices_2 = hdim2_indices

    if PBC_flag == "hdim_1":
        # ONLY periodic in y

        if ((np.max(hdim1_indices)) == y_max) and ((np.min(hdim1_indices) == y_min)):
            for y2 in range(0, len(hdim1_indices_2)):
                h1_ind = hdim1_indices_2[y2]
                if h1_ind < (y_max / 2):
                    hdim1_indices_2[y2] = h1_ind + y_max

    elif PBC_flag == "hdim_2":
        # ONLY periodic in x

        if ((np.max(hdim2_indices)) == x_max) and ((np.min(hdim2_indices) == x_min)):
            for x2 in range(0, len(hdim2_indices_2)):
                h2_ind = hdim2_indices_2[x2]
                if h2_ind < (x_max / 2):
                    hdim2_indices_2[x2] = h2_ind + x_max

    elif PBC_flag == "both":
        # DOUBLY periodic boundaries

        if ((np.max(hdim1_indices)) == y_max) and ((np.min(hdim1_indices) == y_min)):
            for y2 in range(0, len(hdim1_indices_2)):
                h1_ind = hdim1_indices_2[y2]
                if h1_ind < (y_max / 2):
                    hdim1_indices_2[y2] = h1_ind + y_max

        if ((np.max(hdim2_indices)) == x_max) and ((np.min(hdim2_indices) == x_min)):
            for x2 in range(0, len(hdim2_indices_2)):
                h2_ind = hdim2_indices_2[x2]
                if h2_ind < (x_max / 2):
                    hdim2_indices_2[x2] = h2_ind + x_max

    hdim1_indices = hdim1_indices_2
    hdim2_indices = hdim2_indices_2

    if len(region_bbox) == 4:
        # 2D case
        is_3D = False
        track_data_region = track_data[
            region_bbox[0] : region_bbox[2], region_bbox[1] : region_bbox[3]
        ]
    elif len(region_bbox) == 6:
        # 3D case
        is_3D = True
        track_data_region = track_data[
            region_bbox[0] : region_bbox[3],
            region_bbox[1] : region_bbox[4],
            region_bbox[2] : region_bbox[5],
        ]

    if position_threshold == "center":
        # get position as geometrical centre of identified region:
        hdim1_index = np.mean(hdim1_indices)
        hdim2_index = np.mean(hdim2_indices)
        if is_3D:
            vdim_index = np.mean(vdim_indices)

    elif position_threshold == "extreme":
        # get position as max/min position inside the identified region:
        if target == "maximum":
            index = np.argmax(track_data_region[region_small])
        if target == "minimum":
            index = np.argmin(track_data_region[region_small])
        hdim1_index = hdim1_indices[index]
        hdim2_index = hdim2_indices[index]
        if is_3D:
            vdim_index = vdim_indices[index]

    elif position_threshold == "weighted_diff":
        # get position as centre of identified region, weighted by difference from the threshold:
        weights = abs(track_data_region[region_small] - threshold_i)
        if sum(weights) == 0:
            weights = None
        hdim1_index = np.average(hdim1_indices, weights=weights)
        hdim2_index = np.average(hdim2_indices, weights=weights)
        if is_3D:
            vdim_index = np.average(vdim_indices, weights=weights)

    elif position_threshold == "weighted_abs":
        # get position as centre of identified region, weighted by absolute values if the field:
        weights = abs(track_data_region[region_small])
        if sum(weights) == 0:
            weights = None
        hdim1_index = np.average(hdim1_indices, weights=weights)
        hdim2_index = np.average(hdim2_indices, weights=weights)
        if is_3D:
            vdim_index = np.average(vdim_indices, weights=weights)

    else:
        raise ValueError(
            "position_threshold must be center,extreme,weighted_diff or weighted_abs"
        )

    # re-transform of any coords beyond the boundaries - (should be) general enough to work for any variety of PBC
    # as no x or y points will be beyond the boundaries if we haven't transformed them in the first place
    if (PBC_flag == "hdim_1") or (PBC_flag == "hdim_2") or (PBC_flag == "both"):
        if hdim1_index > y_max:
            hdim1_index = hdim1_index - y_max

        if hdim2_index > x_max:
            hdim2_index = hdim2_index - x_max

    if is_3D:
        return vdim_index, hdim1_index, hdim2_index
    else:
        return hdim1_index, hdim2_index


def test_overlap(region_inner, region_outer):
    """Test for overlap between two regions

    Parameters
    ----------
    region_1 : list
        list of 2-element tuples defining the indices of
        all cell in the region

    region_2 : list
        list of 2-element tuples defining the indices of
        all cell in the region

    Returns
    ----------
    overlap : bool
        True if there are any shared points between the two
        regions
    """

    overlap = frozenset(region_outer).isdisjoint(region_inner)
    return not overlap


def remove_parents(features_thresholds, regions_i, regions_old):
    """Remove parents of newly detected feature regions.

    Remove features where its regions surround newly
    detected feature regions.

    Parameters
    ----------
    features_thresholds : pandas.DataFrame
        Dataframe containing detected features.

    regions_i : dict
        Dictionary containing the regions above/below
        threshold for the newly detected feature
        (feature ids as keys).

    regions_old : dict
        Dictionary containing the regions above/below
        threshold from previous threshold
        (feature ids as keys).

    Returns
    -------
    features_thresholds : pandas.DataFrame
        Dataframe containing detected features excluding those
        that are superseded by newly detected ones.
    """

    try:
        all_curr_pts = np.concatenate([vals for idx, vals in regions_i.items()])
        all_old_pts = np.concatenate([vals for idx, vals in regions_old.items()])
    except ValueError:
        # the case where there are no regions
        return features_thresholds
    old_feat_arr = np.empty((len(all_old_pts)))
    curr_loc = 0
    for idx_old in regions_old:
        old_feat_arr[curr_loc : curr_loc + len(regions_old[idx_old])] = idx_old
        curr_loc += len(regions_old[idx_old])

    common_pts, common_ix_new, common_ix_old = np.intersect1d(
        all_curr_pts, all_old_pts, return_indices=True
    )
    list_remove = np.unique(old_feat_arr[common_ix_old])

    # remove parent regions:
    if features_thresholds is not None:
        features_thresholds = features_thresholds[
            ~features_thresholds["idx"].isin(list_remove)
        ]

    return features_thresholds


def feature_detection_threshold(
    data_i,
    i_time,
    threshold=None,
    min_num=0,
    target="maximum",
    position_threshold="center",
    sigma_threshold=0.5,
    n_erosion_threshold=0,
    n_min_threshold=0,
    min_distance=0,
    idx_start=0,
    PBC_flag="none",
    vertical_axis=None,
):
    """Find features based on individual threshold value.

    Parameters
    ----------
    data_i : iris.cube.Cube
        2D field to perform the feature detection (single timestep) on.

    i_time : int
        Number of the current timestep.

    threshold : float, optional
        Threshold value used to select target regions to track. Default
                is None.

    target : {'maximum', 'minimum'}, optional
        Flag to determine if tracking is targetting minima or maxima
        in the data. Default is 'maximum'.

    position_threshold : {'center', 'extreme', 'weighted_diff',
                          'weighted_abs'}, optional
        Flag choosing method used for the position of the tracked
        feature. Default is 'center'.

    sigma_threshold: float, optional
        Standard deviation for intial filtering step. Default is 0.5.

    n_erosion_threshold: int, optional
        Number of pixel by which to erode the identified features.
        Default is 0.

    n_min_threshold : int, optional
        Minimum number of identified features. Default is 0.

    min_distance : float, optional
        Minimum distance between detected features. Default is 0.

    idx_start : int, optional
        Feature id to start with. Default is 0.

    PBC_flag: str('none', 'hdim_1', 'hdim_2', 'both')
        flag sets how to treat boundaries (i.e., whether they are periodic or not)
        'none' - no PBCs
        'hdim_1' - periodic in hdim1 ONLY
        'hdim_2' - periodic in hdim2 ONLY
        'both' - DOUBLY periodic
    vertical_axis: int
        The vertical axis number of the data.


    Returns
    -------
    features_threshold : pandas DataFrame
        Detected features for individual threshold.

    regions : dict
        Dictionary containing the regions above/below threshold used
        for each feature (feature ids as keys).
    """

    from skimage.measure import label
    from skimage.morphology import binary_erosion
    from copy import deepcopy

    if min_num != 0:
        warnings.warn(
            "min_num parameter has no effect and will be deprecated in a future version of tobac. Please use n_min_threshold instead",
            FutureWarning,
        )

    # If we are given a 3D data array, we should do 3D feature detection.
    is_3D = len(data_i.shape) == 3

    # We need to transpose the input data
    if is_3D:
        if vertical_axis == 1:
            data_i = np.transpose(data_i, axes=(1, 0, 2))
        elif vertical_axis == 2:
            data_i = np.transpose(data_i, axes=(2, 0, 1))

    # if looking for minima, set values above threshold to 0 and scale by data minimum:
    if target == "maximum":
        mask = data_i >= threshold
        # if looking for minima, set values above threshold to 0 and scale by data minimum:
    elif target == "minimum":
        mask = data_i <= threshold
    # only include values greater than threshold
    # erode selected regions by n pixels
    if n_erosion_threshold > 0:
        if is_3D:
            selem = np.ones(
                (n_erosion_threshold, n_erosion_threshold, n_erosion_threshold)
            )
        else:
            selem = np.ones((n_erosion_threshold, n_erosion_threshold))
        mask = binary_erosion(mask, selem).astype(bool)
        # detect individual regions, label  and count the number of pixels included:
    labels, num_labels = label(mask, background=0, return_num=True)
    if not is_3D:
        # let's transpose labels to a 1,y,x array to make calculations etc easier.
        labels = labels[np.newaxis, :, :]
    z_min = 0
    z_max = labels.shape[0]
    y_min = 0
    y_max = labels.shape[1] - 1
    x_min = 0
    x_max = labels.shape[2] - 1

    # deal with PBCs
    # all options that involve dealing with periodic boundaries
    pbc_options = ["hdim_1", "hdim_2", "both"]

    # we need to deal with PBCs in some way.
    if PBC_flag in pbc_options:
        #
        # create our copy of `labels` to edit
        labels_2 = deepcopy(labels)
        # points we've already edited
        skip_list = np.array([])
        # labels that touch the PBC walls
        wall_labels = np.array([])

        if num_labels > 0:
            all_label_props = tb_utils.get_label_props_in_dict(labels)
            [
                all_labels_max_size,
                all_label_locs_v,
                all_label_locs_h1,
                all_label_locs_h2,
            ] = tb_utils.get_indices_of_labels_from_reg_prop_dict(all_label_props)

            # find the points along the boundaries

            # along hdim_1 or both horizontal boundaries
            if PBC_flag == "hdim_1" or PBC_flag == "both":
                # north wall
                n_wall = np.unique(labels[:, y_max, :])
                wall_labels = np.append(wall_labels, n_wall)

                # south wall
                s_wall = np.unique(labels[:, y_min, :])
                wall_labels = np.append(wall_labels, s_wall)

            # along hdim_2 or both horizontal boundaries
            if PBC_flag == "hdim_2" or PBC_flag == "both":
                # east wall
                e_wall = np.unique(labels[:, :, x_max])
                wall_labels = np.append(wall_labels, e_wall)

                # west wall
                w_wall = np.unique(labels[:, :, x_min])
                wall_labels = np.append(wall_labels, w_wall)

            wall_labels = np.unique(wall_labels)

            for label_ind in wall_labels:
                # create list for skip labels for this wall label only
                skip_list_thisind = []
                # 0 isn't a real index
                if label_ind == 0:
                    continue
                # skip this label if we have already dealt with it.
                if np.any(label_ind == skip_list):
                    continue

                # get all locations of this label.
                # TODO: harmonize x/y/z vs hdim1/hdim2/vdim.
                label_locs_v = all_label_locs_v[label_ind]
                label_locs_h1 = all_label_locs_h1[label_ind]
                label_locs_h2 = all_label_locs_h2[label_ind]

                # loop through every point in the label
                for label_z, label_y, label_x in zip(
                    label_locs_v, label_locs_h1, label_locs_h2
                ):
                    # check if this is the special case of being a corner point.
                    # if it's doubly periodic AND on both x and y boundaries, it's a corner point
                    # and we have to look at the other corner.
                    # here, we will only look at the corner point and let the below deal with x/y only.
                    if PBC_flag == "both" and (
                        np.any(label_y == [y_min, y_max])
                        and np.any(label_x == [x_min, x_max])
                    ):

                        # adjust x and y points to the other side
                        y_val_alt = tb_utils.adjust_pbc_point(label_y, y_min, y_max)
                        x_val_alt = tb_utils.adjust_pbc_point(label_x, x_min, x_max)

                        label_on_corner = labels[label_z, y_val_alt, x_val_alt]

                        if (label_on_corner != 0) and (
                            ~np.any(label_on_corner == skip_list)
                        ):
                            # alt_inds = np.where(labels==alt_label_3)
                            # get a list of indices where the label on the corner is so we can switch them
                            # in the new list.

                            labels_2[
                                all_label_locs_v[label_on_corner],
                                all_label_locs_h1[label_on_corner],
                                all_label_locs_h2[label_on_corner],
                            ] = label_ind
                            skip_list = np.append(skip_list, label_on_corner)
                            skip_list_thisind = np.append(
                                skip_list_thisind, label_on_corner
                            )

                        # if it's labeled and has already been dealt with for this label
                        elif (
                            (label_on_corner != 0)
                            and (np.any(label_on_corner == skip_list))
                            and (np.any(label_on_corner == skip_list_thisind))
                        ):
                            # print("skip_list_thisind label - has already been treated this index")
                            continue

                        # if it's labeled and has already been dealt with via a previous label
                        elif (
                            (label_on_corner != 0)
                            and (np.any(label_on_corner == skip_list))
                            and (~np.any(label_on_corner == skip_list_thisind))
                        ):
                            # find the updated label, and overwrite all of label_ind indices with updated label
                            labels_2_alt = labels_2[label_z, y_val_alt, x_val_alt]
                            labels_2[
                                label_locs_v, label_locs_h1, label_locs_h2
                            ] = labels_2_alt
                            skip_list = np.append(skip_list, label_ind)
                            break

                    # on the hdim1 boundary and periodic on hdim1
                    if (PBC_flag == "hdim_1" or PBC_flag == "both") and np.any(
                        label_y == [y_min, y_max]
                    ):
                        y_val_alt = tb_utils.adjust_pbc_point(label_y, y_min, y_max)

                        # get the label value on the opposite side
                        label_alt = labels[label_z, y_val_alt, label_x]

                        # if it's labeled and not already been dealt with
                        if (label_alt != 0) and (~np.any(label_alt == skip_list)):
                            # find the indices where it has the label value on opposite side and change their value to original side
                            # print(all_label_locs_v[label_alt], alt_inds[0])
                            labels_2[
                                all_label_locs_v[label_alt],
                                all_label_locs_h1[label_alt],
                                all_label_locs_h2[label_alt],
                            ] = label_ind
                            # we have already dealt with this label.
                            skip_list = np.append(skip_list, label_alt)
                            skip_list_thisind = np.append(skip_list_thisind, label_alt)

                        # if it's labeled and has already been dealt with for this label
                        elif (
                            (label_alt != 0)
                            and (np.any(label_alt == skip_list))
                            and (np.any(label_alt == skip_list_thisind))
                        ):
                            continue

                        # if it's labeled and has already been dealt with
                        elif (
                            (label_alt != 0)
                            and (np.any(label_alt == skip_list))
                            and (~np.any(label_alt == skip_list_thisind))
                        ):
                            # find the updated label, and overwrite all of label_ind indices with updated label
                            labels_2_alt = labels_2[label_z, y_val_alt, label_x]
                            labels_2[
                                label_locs_v, label_locs_h1, label_locs_h2
                            ] = labels_2_alt
                            skip_list = np.append(skip_list, label_ind)
                            break

                    if (PBC_flag == "hdim_2" or PBC_flag == "both") and np.any(
                        label_x == [x_min, x_max]
                    ):
                        x_val_alt = tb_utils.adjust_pbc_point(label_x, x_min, x_max)

                        # get the label value on the opposite side
                        label_alt = labels[label_z, label_y, x_val_alt]

                        # if it's labeled and not already been dealt with
                        if (label_alt != 0) and (~np.any(label_alt == skip_list)):
                            # find the indices where it has the label value on opposite side and change their value to original side
                            labels_2[
                                all_label_locs_v[label_alt],
                                all_label_locs_h1[label_alt],
                                all_label_locs_h2[label_alt],
                            ] = label_ind
                            # we have already dealt with this label.
                            skip_list = np.append(skip_list, label_alt)
                            skip_list_thisind = np.append(skip_list_thisind, label_alt)

                        # if it's labeled and has already been dealt with for this label
                        elif (
                            (label_alt != 0)
                            and (np.any(label_alt == skip_list))
                            and (np.any(label_alt == skip_list_thisind))
                        ):
                            continue

                        # if it's labeled and has already been dealt with
                        elif (
                            (label_alt != 0)
                            and (np.any(label_alt == skip_list))
                            and (~np.any(label_alt == skip_list_thisind))
                        ):
                            # find the updated label, and overwrite all of label_ind indices with updated label
                            labels_2_alt = labels_2[label_z, label_y, x_val_alt]
                            labels_2[
                                label_locs_v, label_locs_h1, label_locs_h2
                            ] = labels_2_alt
                            skip_list = np.append(skip_list, label_ind)
                            break

        # copy over new labels after we have adjusted everything
        labels = labels_2

    elif PBC_flag == "none":
        pass
    else:
        raise ValueError(
            "Options for periodic are currently: none, " + ", ".join(pbc_options)
        )

        # num_labels = num_labels - len(skip_list)
    # END PBC treatment
    # we need to get label properties again after we handle PBCs.
    label_props = tb_utils.get_label_props_in_dict(labels)
    if len(label_props) > 0:
        [
            total_indices_all,
            vdim_indices_all,
            hdim1_indices_all,
            hdim2_indices_all,
        ] = tb_utils.get_indices_of_labels_from_reg_prop_dict(label_props)

    # values, count = np.unique(labels[:,:].ravel(), return_counts=True)
    # values_counts=dict(zip(values, count))
    # Filter out regions that have less pixels than n_min_threshold
    # values_counts={k:v for k, v in values_counts.items() if v>n_min_threshold}

    # check if not entire domain filled as one feature
    if num_labels > 0:
        # create empty list to store individual features for this threshold
        list_features_threshold = list()
        # create empty dict to store regions for individual features for this threshold
        regions = dict()
        # create emptry list of features to remove from parent threshold value

        region = np.empty(mask.shape, dtype=bool)
        # loop over individual regions:
        for cur_idx in total_indices_all:
            # skip this if there aren't enough points to be considered a real feature
            # as defined above by n_min_threshold
            curr_count = total_indices_all[cur_idx]
            if curr_count <= n_min_threshold:
                continue
            if is_3D:
                vdim_indices = vdim_indices_all[cur_idx]
            else:
                vdim_indices = None
            hdim1_indices = hdim1_indices_all[cur_idx]
            hdim2_indices = hdim2_indices_all[cur_idx]

            label_bbox = label_props[cur_idx].bbox
            (
                bbox_zstart,
                bbox_ystart,
                bbox_xstart,
                bbox_zend,
                bbox_yend,
                bbox_xend,
            ) = label_bbox
            bbox_zsize = bbox_zend - bbox_zstart
            bbox_xsize = bbox_xend - bbox_xstart
            bbox_ysize = bbox_yend - bbox_ystart
            # build small region box
            if is_3D:
                region_small = np.full((bbox_zsize, bbox_ysize, bbox_xsize), False)
                region_small[
                    vdim_indices - bbox_zstart,
                    hdim1_indices - bbox_ystart,
                    hdim2_indices - bbox_xstart,
                ] = True

            else:
                region_small = np.full((bbox_ysize, bbox_xsize), False)
                region_small[
                    hdim1_indices - bbox_ystart, hdim2_indices - bbox_xstart
                ] = True
                # we are 2D and need to remove the dummy 3D coordinate.
                label_bbox = (
                    label_bbox[1],
                    label_bbox[2],
                    label_bbox[4],
                    label_bbox[5],
                )

            # [hdim1_indices,hdim2_indices]= np.nonzero(region)
            # write region for individual threshold and feature to dict

            if is_3D:
                region_i = list(
                    zip(
                        hdim1_indices * x_max * z_max
                        + hdim2_indices * z_max
                        + vdim_indices
                    )
                )
            else:
                region_i = np.array(hdim1_indices * x_max + hdim2_indices)

            regions[cur_idx + idx_start] = region_i
            # Determine feature position for region by one of the following methods:
            single_indices = feature_position(
                hdim1_indices,
                hdim2_indices,
                vdim_indices=vdim_indices,
                region_small=region_small,
                region_bbox=label_bbox,
                track_data=data_i,
                threshold_i=threshold,
                position_threshold=position_threshold,
                target=target,
                PBC_flag=PBC_flag,
                x_min=x_min,
                x_max=x_max,
                y_min=y_min,
                y_max=y_max,
            )
            if is_3D:
                vdim_index, hdim1_index, hdim2_index = single_indices
            else:
                hdim1_index, hdim2_index = single_indices
            # create individual DataFrame row in tracky format for identified feature
            appending_dict = {
                "frame": int(i_time),
                "idx": cur_idx + idx_start,
                "hdim_1": hdim1_index,
                "hdim_2": hdim2_index,
                "num": curr_count,
                "threshold_value": threshold,
            }
            column_names = [
                "frame",
                "idx",
                "hdim_1",
                "hdim_2",
                "num",
                "threshold_value",
            ]
            if is_3D:
                appending_dict["vdim"] = vdim_index
                column_names = [
                    "frame",
                    "idx",
                    "vdim",
                    "hdim_1",
                    "hdim_2",
                    "num",
                    "threshold_value",
                ]
            list_features_threshold.append(appending_dict)
        # after looping thru proto-features, check if any exceed num threshold
        # if they do not, provide a blank pandas df and regions dict
        if list_features_threshold == []:
            # print("no features above num value at threshold: ",threshold)
            features_threshold = pd.DataFrame()
            regions = dict()
        # if they do, provide a dataframe with features organized with 2D and 3D metadata
        else:
            # print("at least one feature above num value at threshold: ",threshold)
            # print("column_names, after cur_idx loop: ",column_names)
            features_threshold = pd.DataFrame(
                list_features_threshold, columns=column_names
            )

        # features_threshold=pd.DataFrame(list_features_threshold, columns = column_names)
    else:
        features_threshold = pd.DataFrame()
        regions = dict()

    return features_threshold, regions


def feature_detection_multithreshold_timestep(
    data_i,
    i_time,
    threshold=None,
    min_num=0,
    target="maximum",
    position_threshold="center",
    sigma_threshold=0.5,
    n_erosion_threshold=0,
    n_min_threshold=0,
    min_distance=0,
    feature_number_start=1,
    PBC_flag="none",
    vertical_axis=None,
    dxy=-1,
    wavelength_filtering=None,
):
    """Find features in each timestep.

    Based on iteratively finding regions above/below a set of
    thresholds. Smoothing the input data with the Gaussian filter makes
    output less sensitive to noisiness of input data.

    Parameters
    ----------

    data_i : iris.cube.Cube
        2D field to perform the feature detection (single timestep) on.

    threshold : float, optional
        Threshold value used to select target regions to track. Default
        is None.

    min_num : int, optional
        This parameter is not used in the function. Default is 0.

    target : {'maximum', 'minimum'}, optinal
        Flag to determine if tracking is targetting minima or maxima
        in the data. Default is 'maximum'.

    position_threshold : {'center', 'extreme', 'weighted_diff',
                          'weighted_abs'}, optional
        Flag choosing method used for the position of the tracked
        feature. Default is 'center'.

    sigma_threshold: float, optional
        Standard deviation for intial filtering step. Default is 0.5.

    n_erosion_threshold: int, optional
        Number of pixel by which to erode the identified features.
        Default is 0.

    n_min_threshold : int, optional
        Minimum number of identified features. Default is 0.

    min_distance : float, optional
        Minimum distance between detected features. Default is 0.

    feature_number_start : int, optional
        Feature id to start with. Default is 1.

    PBC_flag : str('none', 'hdim_1', 'hdim_2', 'both')
        Sets whether to use periodic boundaries, and if so in which directions.
        'none' means that we do not have periodic boundaries
        'hdim_1' means that we are periodic along hdim1
        'hdim_2' means that we are periodic along hdim2
        'both' means that we are periodic along both horizontal dimensions

    vertical_axis: int
        The vertical axis number of the data.


    Returns
    -------
    features_threshold : pandas DataFrame
        Detected features for individual timestep.
    """
    # Handle scipy depreciation gracefully
    try:
        from scipy.ndimage import gaussian_filter
    except ImportError:
        from scipy.ndimage.filters import gaussian_filter

    if min_num != 0:
        warnings.warn(
            "min_num parameter has no effect and will be deprecated in a future version of tobac. Please use n_min_threshold instead",
            FutureWarning,
        )

    # get actual numpy array
    track_data = data_i.core_data()

    track_data = gaussian_filter(
        track_data, sigma=sigma_threshold
    )  # smooth data slightly to create rounded, continuous field

    # spectrally filter the input data, if desired
    if wavelength_filtering is not None:
        track_data = spectral_filtering(
            dxy, track_data, wavelength_filtering[0], wavelength_filtering[1]
        )

    # create empty lists to store regions and features for individual timestep
    features_thresholds = pd.DataFrame()
    for i_threshold, threshold_i in enumerate(threshold):
        if i_threshold > 0 and not features_thresholds.empty:
            idx_start = features_thresholds["idx"].max() + feature_number_start
        else:
            idx_start = feature_number_start - 1
        features_threshold_i, regions_i = feature_detection_threshold(
            track_data,
            i_time,
            threshold=threshold_i,
            sigma_threshold=sigma_threshold,
            min_num=min_num,
            target=target,
            position_threshold=position_threshold,
            n_erosion_threshold=n_erosion_threshold,
            n_min_threshold=n_min_threshold,
            min_distance=min_distance,
            idx_start=idx_start,
            PBC_flag=PBC_flag,
            vertical_axis=vertical_axis,
        )
        if any([x is not None for x in features_threshold_i]):
            features_thresholds = features_thresholds.append(features_threshold_i)

        # For multiple threshold, and features found both in the current and previous step, remove "parent" features from Dataframe
        if i_threshold > 0 and not features_thresholds.empty and regions_old:
            # for each threshold value: check if newly found features are surrounded by feature based on less restrictive threshold
            features_thresholds = remove_parents(
                features_thresholds, regions_i, regions_old
            )
        regions_old = regions_i

        logging.debug(
            "Finished feature detection for threshold "
            + str(i_threshold)
            + " : "
            + str(threshold_i)
        )
    return features_thresholds


def feature_detection_multithreshold(
    field_in,
    dxy=None,
    dz=None,
    threshold=None,
    min_num=0,
    target="maximum",
    position_threshold="center",
    sigma_threshold=0.5,
    n_erosion_threshold=0,
    n_min_threshold=0,
    min_distance=0,
    feature_number_start=1,
    PBC_flag="none",
    vertical_coord="auto",
    vertical_axis=None,
    detect_subset=None,
    wavelength_filtering=None,
):

    """Perform feature detection based on contiguous regions.

    The regions are above/below a threshold.

    Parameters
    ----------
    field_in : iris.cube.Cube
        2D field to perform the tracking on (needs to have coordinate
        'time' along one of its dimensions),

    dxy : float
        Grid spacing of the input data (in meter).

    thresholds : list of floats, optional
        Threshold values used to select target regions to track.
        Default is None.

    target : {'maximum', 'minimum'}, optional
        Flag to determine if tracking is targetting minima or maxima in
        the data. Default is 'maximum'.

    position_threshold : {'center', 'extreme', 'weighted_diff',
                          'weighted_abs'}, optional
        Flag choosing method used for the position of the tracked
        feature. Default is 'center'.

    coord_interp_kind : str, optional
        The kind of interpolation for coordinates. Default is 'linear'.
        For 1d interp, {'linear', 'nearest', 'nearest-up', 'zero',
                        'slinear', 'quadratic', 'cubic',
                        'previous', 'next'}.
        For 2d interp, {'linear', 'cubic', 'quintic'}.

    sigma_threshold: float, optional
        Standard deviation for intial filtering step. Default is 0.5.

    n_erosion_threshold: int, optional
        Number of pixel by which to erode the identified features.
        Default is 0.

    n_min_threshold : int, optional
        Minimum number of identified features. Default is 0.

    min_distance : float, optional
        Minimum distance between detected features. Default is 0.

    feature_number_start : int, optional
        Feature id to start with. Default is 1.

    PBC_flag : str('none', 'hdim_1', 'hdim_2', 'both')
        Sets whether to use periodic boundaries, and if so in which directions.
        'none' means that we do not have periodic boundaries
        'hdim_1' means that we are periodic along hdim1
        'hdim_2' means that we are periodic along hdim2
        'both' means that we are periodic along both horizontal dimensions
    vertical_coord: str
        Name or axis number of the vertical coordinate. If 'auto', tries to auto-detect.
        It looks for the coordinate or the dimension name corresponding
        to the string.
    vertical_axis: int or None.
        The vertical axis number of the data. If None, uses vertical_coord
        to determine axis.
    detect_subset: dict-like or None
        Whether to run feature detection on only a subset of the data.
        If this is not None, it will subset the grid that we run feature detection
        on to the range specified for each axis specified. The format of this dict is:
        {axis-number: (start, end)}, where axis-number is the number of the axis to subset,
        start is inclusive, and end is exclusive.
        For example, if your data are oriented as (time, z, y, x) and you want to
        only detect on values between z levels 10 and 29, you would set:
        {1: (10, 30)}.

    Returns
    -------
    features : pandas.DataFrame
        Detected features. The structure of this dataframe is explained
        `here <https://tobac.readthedocs.io/en/latest/data_input.html>`__
    """
    from .utils import add_coordinates, add_coordinates_3D

    logging.debug("start feature detection based on thresholds")

    if "time" not in [coord.name() for coord in field_in.coords()]:
        raise ValueError(
            "input to feature detection step must include a dimension named 'time'"
        )

    # Check whether we need to run 2D or 3D feature detection
    if field_in.ndim == 3:
        logging.debug("Running 2D feature detection")
        is_3D = False
    elif field_in.ndim == 4:
        logging.debug("Running 3D feature detection")
        is_3D = True
    else:
        raise ValueError("Feature detection only works with 2D or 3D data")

    ndim_time = field_in.coord_dims("time")[0]

    if detect_subset is not None:
        raise NotImplementedError("Subsetting feature detection not yet supported.")

    if detect_subset is not None and ndim_time in detect_subset:
        raise NotImplementedError("Cannot subset on time")

    if is_3D:
        # We need to determine the time axis so that we can determine the
        # vertical axis in each timestep if vertical_axis is not none.
        if vertical_axis is not None:
            # We only need to adjust the axis number if the time axis
            # is a lower axis number than the specified vertical coordinate.
            if ndim_time < vertical_axis:
                vertical_axis = vertical_axis - 1
        else:
            # We need to determine vertical axis
            vertical_axis = tb_utils.find_vertical_axis_from_coord(
                field_in, vertical_coord=vertical_coord
            )

    # create empty list to store features for all timesteps
    list_features_timesteps = []

    # loop over timesteps for feature identification:
    data_time = field_in.slices_over("time")

    # if single threshold is put in as a single value, turn it into a list
    if type(threshold) in [int, float]:
        threshold = [threshold]

    # if wavelength_filtering is given, check that value cannot be larger than distances along x and y,
    # that the value cannot be smaller or equal to the grid spacing
    # and throw a warning if dxy and wavelengths have about the same order of magnitude
    # TODO: fix wavelength filtering axes
    if wavelength_filtering is not None:
        distance_x = field_in.shape[1] * (dxy)
        distance_y = field_in.shape[2] * (dxy)
        distance = min(distance_x, distance_y)

        # make sure the smaller value is taken as the minimum and the larger as the maximum
        lambda_min = min(wavelength_filtering)
        lambda_max = max(wavelength_filtering)

        if lambda_min > distance or lambda_max > distance:
            raise ValueError(
                "The given wavelengths cannot be larger than the total distance in m along the axes of the domain."
            )

        elif lambda_min <= dxy:
            raise ValueError(
                "The given minimum wavelength cannot be smaller than gridspacing dxy. Please note that both dxy and the values for wavelength_filtering should be given in meter."
            )

        elif np.floor(np.log10(lambda_min)) - np.floor(np.log10(dxy)) > 1:
            warnings.warn(
                "Warning: The values for dxy and the minimum wavelength are close in order of magnitude. Please note that both dxy and for wavelength_filtering should be given in meter."
            )

    for i_time, data_i in enumerate(data_time):
        time_i = data_i.coord("time").units.num2date(data_i.coord("time").points[0])

        features_thresholds = feature_detection_multithreshold_timestep(
            data_i,
            i_time,
            threshold=threshold,
            sigma_threshold=sigma_threshold,
            min_num=min_num,
            target=target,
            position_threshold=position_threshold,
            n_erosion_threshold=n_erosion_threshold,
            n_min_threshold=n_min_threshold,
            min_distance=min_distance,
            feature_number_start=feature_number_start,
            PBC_flag=PBC_flag,
            vertical_axis=vertical_axis,
            dxy=dxy,
            wavelength_filtering=wavelength_filtering,
        )
        # check if list of features is not empty, then merge features from different threshold values
        # into one DataFrame and append to list for individual timesteps:
        if not features_thresholds.empty:
            # Loop over DataFrame to remove features that are closer than distance_min to each other:
            if min_distance > 0:
                features_thresholds = filter_min_distance(
                    features_thresholds,
                    dxy=dxy,
                    dz=dz,
                    min_distance=min_distance,
                    z_coordinate_name=vertical_coord,
                )
        list_features_timesteps.append(features_thresholds)

        logging.debug(
            "Finished feature detection for " + time_i.strftime("%Y-%m-%d_%H:%M:%S")
        )

    logging.debug("feature detection: merging DataFrames")
    # Check if features are detected and then concatenate features from different timesteps into one pandas DataFrame
    # If no features are detected raise error
    if any([not x.empty for x in list_features_timesteps]):
        features = pd.concat(list_features_timesteps, ignore_index=True)
        features["feature"] = features.index + feature_number_start
        #    features_filtered = features.drop(features[features['num'] < min_num].index)
        #    features_filtered.drop(columns=['idx','num','threshold_value'],inplace=True)
        if "vdim" in features:
            features = add_coordinates_3D(
                features, field_in, vertical_coord=vertical_coord
            )
        else:
            features = add_coordinates(features, field_in)
    else:
        features = None
        logging.debug("No features detected")
    logging.debug("feature detection completed")
    return features


def filter_min_distance(
    features,
    dxy=None,
    dz=None,
    min_distance=None,
    x_coordinate_name=None,
    y_coordinate_name=None,
    z_coordinate_name=None,
    PBC_flag="none",
    max_h1=0,
    max_h2=0,
):
    """Function to remove features that are too close together.
    If two features are closer than `min_distance`, it keeps the
    larger feature.

    TODO: does this function work with minima?

    Parameters
    ----------
    features:      pandas DataFrame
                   features
    dxy:           float
        Constant horzontal grid spacing (m), optional. If not specified,
        this function requires that ```x_coordinate_name``` and
        ```y_coordinate_name``` are available in `features`. If you specify a
        value here, this function assumes that it is the x/y spacing between points
        even if ```x_coordinate_name``` and ```y_coordinate_name``` are specified.
    dz: float
        Constant vertical grid spacing (m), optional. If not specified
        and the input is 3D, this function requires that `altitude` is available
        in the `features` input. If you specify a value here, this function assumes
        that it is the constant z spacing between points, even if ```z_coordinate_name```
        is specified.
    min_distance:  float
        minimum distance between detected features (m)
    x_coordinate_name: str
        The name of the x coordinate to calculate distance based on in meters.
        This is typically `projection_x_coordinate`
    y_coordinate_name: str
        The name of the y coordinate to calculate distance based on in meters.
        This is typically `projection_y_coordinate`
    z_coordinate_name: str or None
        The name of the z coordinate to calculate distance based on in meters.
        This is typically `altitude`. If `auto`, tries to auto-detect.
    PBC_flag : str('none', 'hdim_1', 'hdim_2', 'both')
        Sets whether to use periodic boundaries, and if so in which directions.
        'none' means that we do not have periodic boundaries
        'hdim_1' means that we are periodic along hdim1
        'hdim_2' means that we are periodic along hdim2
        'both' means that we are periodic along both horizontal dimensions
    max_h1: int
        Maximum coordinate in the hdim_1 dimension if PBC_flag is not 'none'
    max_h2: int
        Maximum coordinate in the hdim_2 dimension if PBC_flag is not 'none'

    Returns
    -------
    pandas DataFrame
        features after filtering
    """

    from itertools import combinations

    remove_list_distance = []

    if PBC_flag != "none":
        raise NotImplementedError("We haven't yet implemented PBCs into this.")

    # if we are 3D, the vertical dimension is in features. if we are 2D, there
    # is no vertical dimension in features.
    is_3D = "vdim" in features

    if is_3D and dz is None:
        z_coordinate_name = tb_utils.find_dataframe_vertical_coord(
            features, z_coordinate_name
        )

    # Check if both dxy and their coordinate names are specified.
    # If they are, warn that we will use dxy.
    if dxy is not None and (
        x_coordinate_name in features and y_coordinate_name in features
    ):
        warnings.warn(
            "Both " + x_coordinate_name + "/" + y_coordinate_name + " and dxy "
            "set. Using constant dxy. Set dxy to None if you want to use the "
            "interpolated coordinates, or set `x_coordinate_name` and "
            "`y_coordinate_name` to None to use a constant dxy."
        )

    # Check and if both dz is specified and altitude is available, warn that we will use dz.
    if is_3D and (dz is not None and z_coordinate_name in features):
        warnings.warn(
            "Both "
            + z_coordinate_name
            + " and dz available to filter_min_distance; using constant dz. "
            "Set dz to none if you want to use altitude or set `z_coordinate_name` to None to use constant dz."
        )

    # create list of tuples with all combinations of features at the timestep:
    indeces = combinations(features.index.values, 2)
    # Loop over combinations to remove features that are closer together than min_distance and keep larger one (either higher threshold or larger area)
    for index_1, index_2 in indeces:
        if index_1 is not index_2:
            if is_3D:
                if dz is not None:
                    z_coord_1 = dz * features.loc[index_1, "vdim"]
                    z_coord_2 = dz * features.loc[index_2, "vdim"]
                else:
                    z_coord_1 = features.loc[index_1, z_coordinate_name]
                    z_coord_2 = features.loc[index_2, z_coordinate_name]

                coord_1 = (
                    z_coord_1,
                    dxy * features.loc[index_1, "hdim_1"],
                    dxy * features.loc[index_1, "hdim_2"],
                )
                coord_2 = (
                    z_coord_2,
                    dxy * features.loc[index_2, "hdim_1"],
                    dxy * features.loc[index_2, "hdim_2"],
                )
            else:
                coord_1 = (
                    dxy * features.loc[index_1, "hdim_1"],
                    dxy * features.loc[index_1, "hdim_2"],
                )
                coord_2 = (
                    dxy * features.loc[index_2, "hdim_1"],
                    dxy * features.loc[index_2, "hdim_2"],
                )

            distance = tb_utils.calc_distance_coords_pbc(
                coords_1=np.array(coord_1),
                coords_2=np.array(coord_2),
                min_h1=0,
                max_h1=max_h1,
                min_h2=0,
                max_h2=max_h2,
                PBC_flag=PBC_flag,
            )

            if distance <= min_distance:
                # print(distance, min_distance, index_1, index_2, features.size)
                #                        logging.debug('distance<= min_distance: ' + str(distance))
                if (
                    features.loc[index_1, "threshold_value"]
                    > features.loc[index_2, "threshold_value"]
                ):
                    remove_list_distance.append(index_2)
                elif (
                    features.loc[index_1, "threshold_value"]
                    < features.loc[index_2, "threshold_value"]
                ):
                    remove_list_distance.append(index_1)
                elif (
                    features.loc[index_1, "threshold_value"]
                    == features.loc[index_2, "threshold_value"]
                ):
                    if features.loc[index_1, "num"] > features.loc[index_2, "num"]:
                        remove_list_distance.append(index_2)
                    elif features.loc[index_1, "num"] < features.loc[index_2, "num"]:
                        remove_list_distance.append(index_1)
                    elif features.loc[index_1, "num"] == features.loc[index_2, "num"]:
                        remove_list_distance.append(index_2)
    features = features[~features.index.isin(remove_list_distance)]
    return features
