#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Mar 15 18:02:17 2024

@author: justin
"""
import os
import csv
import numpy as np
import numpy.typing as npt
from typing import List
from src import analysis_window
from src import curves
from src import fitting
from src import quant_data


class AnalysisManager:
    """
    Takes responsibility for communicating between different elements of the
    analysis window. Created by App.

    Takes file manager because it needs to know which file is active.

    In a MVC architecture, this class would represent the controller.

    Attributes:
        file_manager: The object that knows which file is active.
        app: The main entry point into the app.
        analysis_window: The tk.TopLevel window that contains the graph.
        graph_manager: The graph frame within the window.
        message_bar: Displays messages underneath the graph.
        info_box: Displays information on plotted curves.
        gauss_width: None or float. If None, all gaussians will have the same
                     width. Switched by the graph toolbar.
    """
    def __init__(self, file_manager, app):
        self.file_manager = file_manager
        self.app = app

        self.analysis_window = analysis_window.AnalysisWindow(self)
        self.graph_manager = self.analysis_window.graph_manager
        self.message_bar = self.analysis_window.message_bar
        self.info_box = self.analysis_window.info_box

        self.gauss_width: None | float = None

        self.update()



    def get_active_qd(self) -> quant_data.QuantData:
        """
        Passthrough method to get qd object from file manager. Used to reduce
        number of objects talking directly to file manager.
        """
        return self.file_manager.get_active_qd()



    def gauss_widths_locked(self) -> bool:
        """
        Denotes whether all gaussian widths are currently fixed to the same
        value or not.
        """
        return self.gauss_width is not None



    def update(self) -> None:
        """
        Creates a new composite_curve in the active QuantData object, then
        updates the info_box and graph.
        """
        self._init_composite_fit()
        self.update_gauss_table()
        self.graph_manager.active_qd_changed()



    def _init_composite_fit(self) -> None:
        """
        Instantiates a CompositeCurve with a default Constant curve for the
        active QuantData object.
        """
        qd = self.get_active_qd()
        if qd.composite_curve is None:
            qd.composite_curve = curves.CompositeCurve()
            qd.composite_curve.curve_list.append(curves.Constant(1))



    def reset_fit(self) -> None:
        """
        Reinitializes The QuantData object's CompositeCurve. Called by
        graph toolbar.
        """
        qd = self.get_active_qd()
        if qd.composite_curve is not None:
            qd.composite_curve = None
        self.update()
        self.set_message("Fit reset.")



    def handle_moved(
            self,
            curve: curves.Curve,
            current_xy: npt.NDArray[np.float64]) -> None:
        """
        Updates a Gaussian curve after its handle is moved. Then, updates
        its line and handle, the composite curve, the info box, and sends a
        message. Called by HandleManager.

        Args:
            curve: A Curve object which needs to have a set_params() method.
            current_xy: Position during click-and-drag in plot units [x, y].
        """
        x, y = current_xy
        if len(curve.get_params()) > 1:
            curve.set_params(xc=x, A=y)
        else:
            curve.set_params(y=y)
        self.graph_manager.update_handle(curve, draw=False)
        self.graph_manager.update_line(curve, draw=False)
        self.graph_manager.update_composite_curve_line(draw=True)



    def handle_moved_shift(
            self,
            curve: curves.Curve,
            current_xy: npt.NDArray[np.float64],
            clickpoint: npt.NDArray[np.float64]) -> None:
        """
        Updates gaussian amplitude and width based on mouse movements. If
        gaussian widths are currently fixed, modifies all gaussian widths.
        Called by HandleManager.

        Args:
            curve: A Curve object which needs to have a set_params() method.
            current_xy: Position during click-and-drag in plot units [x, y].
            clickpoint: Position of initial click in plot units [x, y].
        """
        x, y = current_xy
        dx, dy = clickpoint - current_xy
        if len(curve.get_params()) > 1: # Avoids baselines.
            updated_width = dx
            curve.set_params(A=y, w=updated_width)
            if self.gauss_widths_locked():
                self.gauss_width = updated_width
                self._update_all_widths()

        else:
            curve.set_params(y=y)
        self.graph_manager.update_handle(curve, draw=False)
        self.graph_manager.update_line(curve, draw=False)
        self.graph_manager.update_composite_curve_line(draw=True)



    def fix_gauss_widths(self) -> None:
        """
        Sets width of all gauss to self.gauss_width, or, if missing, the
        width of the first gaussian in the list.
        """
        qd = self.get_active_qd()
        curve_list = qd.composite_curve.curve_list
        if len(curve_list) > 1: # 1st curve is always the baseline.

            # Toggles back to unfixed if gauss widths are already fixed.
            if self.gauss_widths_locked():
                self.gauss_width = None
                return

            else:
                # All gaussians are set to the width of the first one.
                self.gauss_width = curve_list[1].w

            self._update_all_widths()
            self.set_message(f"Gaussian widths fixed to {self.gauss_width:.2f}")



    def _update_all_widths(self) -> None:
        """
        Sets the width of all Gaussian curves to the value of self.gauss_width.
        self.gauss_width can be None, so self.gauss_width_locked should always
        be True when calling this helper function.
        """
        qd = self.get_active_qd()
        curve_list = qd.composite_curve.curve_list
        if len(curve_list) > 1:
            for curve in curve_list:
                if len(curve.get_params()) > 1:
                    curve.w = self.gauss_width
                    self.graph_manager.update_line(curve)
            self.graph_manager.update_composite_curve_line()
            self.update_gauss_table()



    def optimize_fit(self) -> None:
        """
        Optimizes the fit of the current QuantData's CompositeCurve.
        """
        qd = self.get_active_qd()
        try:
            optimized_curve = fitting.optimize_fit(qd.x, qd.y, qd.composite_curve)
            qd.composite_curve = optimized_curve
            self.set_message("Fit found.")
            self.graph_manager.fit_changed()
            self.update_gauss_table()

        except RuntimeError:
            self.set_message("An optimal fit was not found!")

        except Exception:
            self.set_message("An error ocurred during fitting.")
            raise



    def estimate_fit(self):
        """
        Finds zero points in the QuantData data to guess new gaussian curves
        from scratch.
        """
        qd = self.get_active_qd()
        try:
            composite_curve = fitting.estimate_fit(qd.x, qd.y)
            qd.composite_curve = composite_curve
        except:
            self.set_message("An estimate could not be calculated for some reason!")
            return

        self.optimize_fit()



    def set_message(self, content: str) -> None:
        """ Displays a message in the message bar. """
        self.message_bar.set_message(content)



    def update_gauss_table(self):
        """
        Gets the current parameters for all curves and displays them in the
        info box.
        """
        content = self.get_gauss_table()
        self.info_box.set_info(content)



    def get_gauss_table(self) -> str:
        """
        Returns a tab-delimited table (str) containing params for all
        gaussian curves.
        """
        qd = self.get_active_qd()
        curve_param_list = get_curve_param_list(qd)

        header = ["Peak", "y0", "Area", "xc", "Amp", "w"]
        table = "\t".join(header) + "\n"

        for curve_params in curve_param_list:
            table += str(curve_params[0]) + "\t"
            for param in curve_params[1:]:
                table += f"{param:g}\t"
            table += "\n"

        return table



    def export(self) -> None:
        """
        Gets the current parameters for all curves and exports them to two
        csv files, export.csv and areas.csv, and saves the currently displayed
        graph image as {filename}.png. All files thrown in the same directory
        as the currently active QuantData object.
        """
        qd = self.get_active_qd()
        export_directory = os.path.dirname(qd.path)

        self._export_gauss_table(qd, export_directory)
        self._export_areas(qd, export_directory)
        self._export_image(qd, export_directory)
        self.set_message("Wrote to 'export.csv' and 'areas.csv'. Image saved.")



    def _export_gauss_table(
            self,
            qd: quant_data.QuantData,
            export_directory: str) -> None:
        """
        Writes a csv file to the directory containing the qd data file.
        If file exists, appends to bottom. File contains params of all curves.
        """
        curve_param_list = get_curve_param_list(qd)
        export_filename = "export.csv"
        export_path = os.path.join(export_directory, export_filename)
        export_file_exists = os.path.isfile(export_path)
        csvfile = open(export_path, 'a', newline="")

        fieldnames = ["filename", "Peak", "y0", "Area", "xc", "Amp", "w"]
        writer = csv.writer(csvfile)
        if not export_file_exists:
            writer.writerow(fieldnames)
        writer.writerow("")

        for curve_params in curve_param_list:
            row = [qd.name] + curve_params
            writer.writerow(row)



    def _export_areas(
            self,
            qd: quant_data.QuantData,
            export_directory: str) -> None:
        """
        Writes a csv file to the directory containing the qd data file.
        If file exists, appends to the bottom. File contains calculated areas
        under all curves.
        """
        curve_param_list = get_curve_param_list(qd)
        export_filename = "areas.csv"
        export_path = os.path.join(export_directory, export_filename)
        export_file_exists = os.path.isfile(export_path)
        csvfile = open(export_path, 'a', newline="")

        fieldnames = ("Filename","Peak 1","Peak 2","Peak 3","Peak 4","Peak 5","Peak 6")
        writer = csv.writer(csvfile)
        if not export_file_exists:
            writer.writerow(fieldnames)

        row = []
        row.append(qd.name)

        for curve_params in curve_param_list:
            row.append(curve_params[2])
        writer.writerow(row)



    def _export_image(
            self,
            qd: quant_data.QuantData,
            export_directory: str) -> None:
        """
        Saves the currently displayed graph as a .png image in the directory
        containing the qd data file. File name is {graph_title}.png. If
        file already exists, overwrites.
        """
        export_filename = qd.name + ".png"
        export_path = os.path.join(export_directory, export_filename)
        self.graph_manager.fig.savefig(export_path)



    def export_image_svg(self)-> None:
        """
        Saves the currently displayed graph as a .svg image in the directory
        containing the qd data file. File name is {graph_title}.svg. If
        file already exists, overwrites.
        """
        qd = self.get_active_qd()
        export_directory = os.path.dirname(qd.path)
        export_filename = qd.name + ".svg"
        export_path = os.path.join(export_directory, export_filename)
        self.graph_manager.fig.savefig(export_path)



    def add_gaussian(self, xc: float, A: float, w: float = None) -> None:
        """
        Instantiates a Gaussian object and adds it to the currently active
        QuantData object's CompositeCurve. Called by GraphManager.

        xc (float): The center of the gaussian on the X-axis.
        A (float): Amplitude of the gaussian.
        w (float) (optional): Width of the gaussian.
        """
        qd = self.file_manager.get_active_qd()
        if w is None:
            if self.gauss_width is None:
                w = default_gaussian_width(qd.x[0], qd.x[-1])
            else:
                w = self.gauss_width

        new_gaussian = curves.Gaussian(xc=xc, A=A, w=w)
        qd.composite_curve.curve_list.append(new_gaussian)
        self.update_gauss_table()
        self.graph_manager.update_plot()
        self.set_message(f"Gaussian added at ({xc:.2f}, {A:.2f}).")



    def delete_gaussian(self, curve: curves.Gaussian) -> None:
        """
        Removes the provided Gaussian object from the currently active
        QuantData object's CompositeCurve.
        """
        qd = self.file_manager.get_active_qd()
        qd.composite_curve.curve_list.remove(curve)
        self.update_gauss_table()
        self.graph_manager.update_plot()
        self.set_message("Gaussian deleted.")



def default_gaussian_width(xmin:float, xmax:float, division_factor:int = 20) -> float:
    """
    Calculate the default Gaussian width by dividing the x range by a given factor.
    """
    return (xmax - xmin) / division_factor



def get_curve_param_list(qd: quant_data.QuantData) -> List[List[float]]:
    """
    Returns list of lists of curve params, one list for each curve, baseline
    excluded from output.

    curve_param_list = [[peak, y0, area, xc, A, w], ...]
    """
    qd.composite_curve.sort()
    curve_param_list = []
    y0 = None
    peak = 1

    for curve in qd.composite_curve.curve_list:
        area = curve.area()
        params = curve.get_params()

        if len(params) == 1:
            y0 = params[0]
        else:
            curve_info = [peak, y0, area] + list(params)
            curve_param_list.append(curve_info)
            peak += 1

    return curve_param_list
