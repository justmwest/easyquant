#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Mar 19 19:43:28 2024

@author: justin

"""

import os
import sys
import tkinter as tk
from typing import Callable, Dict
from matplotlib.backends.backend_tkagg import NavigationToolbar2Tk
from src import tool_tip


class GraphToolbar(NavigationToolbar2Tk):
    """
    This is the toolbar that rests under the graph. It contains some custom
    tools. The canvas is the analysis window.

    Attributes:
        graph_manager: The graph (tk.Frame) that these tools go underneath.
        analysis_manager: The overall controller for analysis operations.
        buttons: A dict containing buttons. {name: tk.Button}
        img_dir: The directory path (str) where the image files are located.
    """
    def __init__(self, canvas, frame, analysis_manager):
        self.graph_manager = frame
        self.analysis_manager = analysis_manager
        self.img_dir = os.path.join(
            os.path.abspath(sys.argv[0]).replace(sys.argv[0], ""), 'Images')

        # Overwrite default tools. See https://stackoverflow.com/a/23179396
        self.toolitems = ()
        NavigationToolbar2Tk.__init__(self, canvas, frame)

        self.buttons: Dict[str, tk.Button] = {}

        # Same order in which buttons will appear, left to right.
        buttons_to_add=[
            ("reset.png", "Reset", self.analysis_manager.reset_fit,
             "Reset analysis (start over)"),

            ("undo.png", "Undo", self.graph_manager.undo, "Undo (z)"),
            ("redo.png", "Redo", self.graph_manager.redo, "Redo (r)"),

            ("estimate.gif" , "Estimate" , self.analysis_manager.estimate_fit,
             "Estimate a curve fit (e)"),

            ("fit.gif", "Fit", self.analysis_manager.optimize_fit,
             "Fit from current state (f)"),

            ("save.png", "Save", self.analysis_manager.export,
             "Send to output table(s)"),

            ("save_svg.png", "Save SVG", self.analysis_manager.export_image_svg,
             "Save the current image as an SVG file."),

            ("gauss_unlocked.png", "Fix widths", self.fix_gauss_widths,
             "Fix gaussian widths.")
            ]

        for image_filename, name, command, tooltip in buttons_to_add:
            button = self.add_button(image_filename, name, command, tooltip)
            self.buttons[name] = button



    def filename_to_image(self, filename: str) -> tk.PhotoImage:
        """
        Makes a tk.PhotoImage object from a filename. Refers to icon images
        directory. Filename must contain extension (e.g, 'next.gif' or
        'save.png').
        """
        img_path = os.path.join(self.img_dir, filename)
        img = tk.PhotoImage(master=self, file=img_path)
        return img



    def add_button(self, image_filename: str, name: str,
                   command: Callable, tooltip: str) -> tk.Button:
        """
        Creates and packs a tk.Button object. Returns the created object.

        Args:
            image_filename: Icon image filename (e.g., 'estimate.gif').
            name: Name of the button (for reference in self.buttons dict).
            command: Function called upon button click.
            tooltip: Text to appear upon hover.
        """
        img = self.filename_to_image(image_filename)
        button = tk.Button(master=self, text=name, padx=2, pady=2, image=img,
                           command=command)
        button._ntimage = img
        button.pack(side=tk.LEFT)
        tool_tip.CreateToolTip(button, tooltip)
        return button



    def fix_gauss_widths(self) -> None:
        """
        Asks analysis_manager to toggle whether gauss widths are fixed or not,
        and updates the image on the toolbar to match.
        """
        if self.analysis_manager.gauss_widths_locked():
            img = self.filename_to_image("gauss_unlocked.png")
        else:
            img = self.filename_to_image("gauss_locked.png")
        self.buttons["Fix widths"].config(image=img)
        self.buttons["Fix widths"].image = img # Mem. alloc. trick

        self.analysis_manager.fix_gauss_widths()
