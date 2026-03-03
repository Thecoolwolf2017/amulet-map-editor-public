from __future__ import annotations

import os
from typing import Dict, Optional, Tuple

import wx
from wx.lib.scrolledpanel import ScrolledPanel

from amulet_map_editor.programs.edit.plugins.operations.stock_plugins.export_operations.custom_block_remap import (
    ExportBlockRemapRules,
    ExportRemapPreview,
    build_export_remap_table_for_selection,
    collect_export_remap_preview,
    update_export_block_remap_table,
)


def _launch_path(path: str) -> bool:
    try:
        if hasattr(os, "startfile"):
            os.startfile(path)
            return True
    except Exception:
        pass
    try:
        return bool(wx.LaunchDefaultApplication(path))
    except Exception:
        return False


class _RemapPreviewDialog(wx.Dialog):
    def __init__(
        self,
        parent: wx.Window,
        preview: ExportRemapPreview,
        *,
        title: str,
        allow_confirm: bool = False,
        primary_action_label: str = "Continue",
        secondary_action_label: str = "Remap Wizard",
        close_label: str = "Close",
    ):
        super().__init__(
            parent,
            title=title,
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )
        self._preview = preview
        self._allow_confirm = allow_confirm
        # Keep the ID reference alive for the dialog lifetime to avoid wx ID
        # ref-count assertions when the button/window is destroyed.
        self._wizard_result_id_ref = wx.NewIdRef()
        self._wizard_result_id = int(self._wizard_result_id_ref)

        root = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(root)

        unchanged_blocks = preview.custom_block_total - preview.remapped_block_total
        summary_grid = wx.FlexGridSizer(cols=2, hgap=10, vgap=4)
        summary_grid.AddGrowableCol(1, 1)
        summary_rows = (
            ("Chunks scanned:", f"{preview.scanned_chunks}/{preview.total_chunks}"),
            ("Chunk read failures:", str(preview.failed_chunks)),
            ("Custom namespaces found:", str(preview.custom_namespace_count)),
            ("Custom block ids found:", str(preview.custom_block_count)),
            ("Custom placed blocks:", f"{preview.custom_block_total:,}"),
            ("Will be remapped:", f"{preview.remapped_block_total:,}"),
            ("Kept unchanged:", f"{unchanged_blocks:,}"),
            ("Remap enabled:", "Yes" if preview.remap_enabled else "No"),
            (
                "Auto remap new custom blocks:",
                "Yes" if preview.auto_block_remap else "No",
            ),
        )
        for label, value in summary_rows:
            summary_grid.Add(wx.StaticText(self, label=label), 0, wx.ALIGN_CENTER_VERTICAL)
            summary_grid.Add(wx.StaticText(self, label=value), 0, wx.ALIGN_CENTER_VERTICAL)
        root.Add(summary_grid, 0, wx.ALL | wx.EXPAND, 8)

        self._show_changed_only = wx.CheckBox(
            self, label="Show only entries that remap to a different block"
        )
        self._show_changed_only.Bind(wx.EVT_CHECKBOX, self._refresh_entry_list)
        root.Add(self._show_changed_only, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

        self._entry_list = wx.ListCtrl(
            self, style=wx.LC_REPORT | wx.BORDER_THEME | wx.LC_HRULES | wx.LC_VRULES
        )
        self._entry_list.InsertColumn(0, "Custom Block")
        self._entry_list.InsertColumn(1, "Export As")
        self._entry_list.InsertColumn(2, "Count", wx.LIST_FORMAT_RIGHT)
        self._entry_list.InsertColumn(3, "Action")
        root.Add(self._entry_list, 1, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 8)

        root.Add(
            wx.StaticText(
                self,
                label=(
                    "Legend: green rows are remapped, gray rows are kept unchanged."
                ),
            ),
            0,
            wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND,
            8,
        )
        root.Add(
            wx.StaticText(self, label=f"Remap table: {preview.rules_path}"),
            0,
            wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND,
            8,
        )

        button_row = wx.BoxSizer(wx.HORIZONTAL)
        open_button = wx.Button(self, label="Open JSON File")
        open_button.Bind(wx.EVT_BUTTON, self._open_rules_file)
        button_row.Add(open_button, 0, wx.ALL, 5)
        button_row.AddStretchSpacer()

        if allow_confirm:
            confirm_button = wx.Button(self, wx.ID_YES, primary_action_label)
            confirm_button.Bind(wx.EVT_BUTTON, lambda _evt: self._close_with_result(wx.ID_YES))
            confirm_button.SetDefault()
            button_row.Add(confirm_button, 0, wx.ALL, 5)
            wizard_button = wx.Button(self, wx.ID_NO, "Remap Wizard")
            wizard_button.SetLabel(secondary_action_label)
            wizard_button.Bind(wx.EVT_BUTTON, lambda _evt: self._close_with_result(wx.ID_NO))
            button_row.Add(wizard_button, 0, wx.ALL, 5)
            cancel_button = wx.Button(self, wx.ID_CANCEL, "Cancel")
            cancel_button.Bind(wx.EVT_BUTTON, lambda _evt: self._close_with_result(wx.ID_CANCEL))
            button_row.Add(cancel_button, 0, wx.ALL, 5)
            self.SetAffirmativeId(wx.ID_YES)
            self.SetEscapeId(wx.ID_CANCEL)
        else:
            wizard_button = wx.Button(
                self, self._wizard_result_id, "Open Remap Wizard"
            )
            wizard_button.Bind(
                wx.EVT_BUTTON,
                lambda _evt: self._close_with_result(self._wizard_result_id),
            )
            button_row.Add(wizard_button, 0, wx.ALL, 5)
            close_button = wx.Button(self, wx.ID_CLOSE, close_label)
            close_button.Bind(wx.EVT_BUTTON, lambda _evt: self._close_with_result(wx.ID_CLOSE))
            close_button.SetDefault()
            button_row.Add(close_button, 0, wx.ALL, 5)
            self.SetAffirmativeId(wx.ID_CLOSE)
            self.SetEscapeId(wx.ID_CLOSE)

        root.Add(button_row, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 4)

        self._refresh_entry_list()
        self.SetMinSize((900, 600))
        self.SetSize((980, 680))
        self.CentreOnParent()

    @property
    def wizard_result_id(self) -> int:
        return self._wizard_result_id

    def _close_with_result(self, result_id: int) -> None:
        if self.IsModal():
            self.EndModal(result_id)
            return
        self.SetReturnCode(result_id)
        self.Close()

    def _refresh_entry_list(self, _evt=None):
        self._entry_list.DeleteAllItems()
        show_changed_only = self._show_changed_only.GetValue()

        visible_rows = 0
        for entry in self._preview.entries:
            remapped = entry.source_block != entry.replacement_block
            if show_changed_only and not remapped:
                continue

            row = self._entry_list.InsertItem(
                self._entry_list.GetItemCount(), entry.source_block
            )
            self._entry_list.SetItem(row, 1, entry.replacement_block)
            self._entry_list.SetItem(row, 2, f"{entry.block_count:,}")
            self._entry_list.SetItem(row, 3, "Remap" if remapped else "Keep")
            self._entry_list.SetItemTextColour(
                row, wx.Colour(20, 120, 20) if remapped else wx.Colour(115, 115, 115)
            )
            visible_rows += 1

        if visible_rows == 0:
            row = self._entry_list.InsertItem(
                0,
                "No remap entries to display."
                if show_changed_only
                else "No custom block entries found in this selection.",
            )
            self._entry_list.SetItem(row, 3, "Info")
            self._entry_list.SetItemTextColour(row, wx.Colour(115, 115, 115))

        self._entry_list.SetColumnWidth(0, 330)
        self._entry_list.SetColumnWidth(1, 330)
        self._entry_list.SetColumnWidth(2, 120)
        self._entry_list.SetColumnWidth(3, 110)

    def _open_rules_file(self, _evt):
        if not _launch_path(self._preview.rules_path):
            wx.MessageBox(
                f"Could not open file:\n{self._preview.rules_path}",
                "Open Failed",
                wx.OK | wx.ICON_WARNING,
            )


class _RemapWizardDialog(wx.Dialog):
    def __init__(self, parent: wx.Window, preview: ExportRemapPreview):
        super().__init__(
            parent,
            title="Custom Block Remap Wizard",
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )
        self._preview = preview
        self._mapping_inputs: Dict[str, wx.TextCtrl] = {}
        self.changed_count = 0

        root = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(root)

        description = wx.StaticText(
            self,
            label=(
                "Edit the export-time mapping for custom blocks in the current selection.\n"
                "Leave a mapping blank to remove its explicit override."
            ),
        )
        root.Add(description, 0, wx.ALL | wx.EXPAND, 8)

        self._enabled_checkbox = wx.CheckBox(self, label="Enable remap table on export")
        self._enabled_checkbox.SetValue(preview.remap_enabled)
        root.Add(self._enabled_checkbox, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

        self._auto_checkbox = wx.CheckBox(
            self,
            label="Auto-generate mappings for newly discovered custom blocks",
        )
        self._auto_checkbox.SetValue(preview.auto_block_remap)
        root.Add(self._auto_checkbox, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

        panel = ScrolledPanel(self, style=wx.TAB_TRAVERSAL | wx.BORDER_THEME)
        panel_sizer = wx.BoxSizer(wx.VERTICAL)
        panel.SetSizer(panel_sizer)

        grid = wx.FlexGridSizer(cols=3, hgap=8, vgap=5)
        grid.AddGrowableCol(2, 1)
        grid.Add(wx.StaticText(panel, label="Custom Block ID"), 0, wx.ALIGN_CENTER_VERTICAL)
        grid.Add(wx.StaticText(panel, label="Count"), 0, wx.ALIGN_CENTER_VERTICAL)
        grid.Add(wx.StaticText(panel, label="Export As"), 0, wx.ALIGN_CENTER_VERTICAL)

        for entry in preview.entries:
            grid.Add(wx.StaticText(panel, label=entry.source_block), 0, wx.ALIGN_CENTER_VERTICAL)
            grid.Add(
                wx.StaticText(panel, label=f"{entry.block_count:,}"),
                0,
                wx.ALIGN_CENTER_VERTICAL,
            )
            mapping_input = wx.TextCtrl(panel, value=entry.replacement_block)
            self._mapping_inputs[entry.source_block] = mapping_input
            grid.Add(mapping_input, 1, wx.EXPAND)

        panel_sizer.Add(grid, 1, wx.ALL | wx.EXPAND, 8)
        panel.SetupScrolling(scroll_x=True, scroll_y=True)
        root.Add(panel, 1, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 8)

        path_label = wx.StaticText(self, label=f"Remap table: {preview.rules_path}")
        root.Add(path_label, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 8)

        button_row = wx.BoxSizer(wx.HORIZONTAL)
        open_button = wx.Button(self, label="Open JSON File")
        open_button.Bind(wx.EVT_BUTTON, self._open_rules_file)
        button_row.Add(open_button, 0, wx.ALL, 5)
        button_row.AddStretchSpacer()
        apply_button = wx.Button(self, wx.ID_OK, "Apply")
        apply_button.Bind(wx.EVT_BUTTON, self._apply)
        button_row.Add(apply_button, 0, wx.ALL, 5)
        cancel_button = wx.Button(self, wx.ID_CANCEL, "Cancel")
        button_row.Add(cancel_button, 0, wx.ALL, 5)
        root.Add(button_row, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 4)

        self.SetMinSize((900, 600))
        self.SetSize((980, 680))
        self.CentreOnParent()

    def _open_rules_file(self, _evt):
        if not _launch_path(self._preview.rules_path):
            wx.MessageBox(
                f"Could not open file:\n{self._preview.rules_path}",
                "Open Failed",
                wx.OK | wx.ICON_WARNING,
            )

    def _apply(self, _evt):
        updates: Dict[str, Optional[str]] = {}
        for source_block, mapping_input in self._mapping_inputs.items():
            value = mapping_input.GetValue().strip()
            updates[source_block] = value if value else None

        try:
            self.changed_count = update_export_block_remap_table(
                self._preview.rules_path,
                block_remap_updates=updates,
                auto_block_remap=self._auto_checkbox.GetValue(),
                enabled=self._enabled_checkbox.GetValue(),
            )
        except Exception as exc:
            wx.MessageBox(
                f"Could not save remap table:\n{exc}",
                "Remap Save Error",
                wx.OK | wx.ICON_ERROR,
            )
            return
        self.EndModal(wx.ID_OK)


class ExportRemapWorkflowMixin:
    def _init_export_remap_workflow(self):
        self._prepared_remap_rules: Optional[ExportBlockRemapRules] = None

        button_row = wx.BoxSizer(wx.HORIZONTAL)
        self._preview_remap_button = wx.Button(self, label="Preview Remap")
        self._preview_remap_button.Bind(wx.EVT_BUTTON, self._preview_remap_button_clicked)
        button_row.Add(self._preview_remap_button, 1, wx.RIGHT | wx.EXPAND, 4)

        self._remap_wizard_button = wx.Button(self, label="Remap Wizard")
        self._remap_wizard_button.Bind(wx.EVT_BUTTON, self._remap_wizard_button_clicked)
        button_row.Add(self._remap_wizard_button, 1, wx.LEFT | wx.EXPAND, 4)

        self._sizer.Add(button_row, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 5)

    def _build_preview(self) -> Tuple[ExportBlockRemapRules, ExportRemapPreview]:
        selection = self.canvas.selection.selection_group
        dimension = self.canvas.dimension
        rules = build_export_remap_table_for_selection(self.world, dimension, selection)
        preview = collect_export_remap_preview(self.world, dimension, selection, rules)
        return rules, preview

    def _remap_preview_title(self) -> str:
        return "Export Remap Preview"

    def _remap_confirm_title(self) -> str:
        return "Confirm Export Remap"

    def _remap_primary_action_label(self) -> str:
        return "Export"

    def _remap_secondary_action_label(self) -> str:
        return "Remap Wizard"

    def _preview_remap_button_clicked(self, _evt):
        rules, preview = self._build_preview()
        dialog = _RemapPreviewDialog(
            self,
            preview,
            title=self._remap_preview_title(),
            allow_confirm=False,
        )
        try:
            result = dialog.ShowModal()
            if result == dialog.wizard_result_id:
                self._open_remap_wizard()
        finally:
            dialog.Destroy()
        self._prepared_remap_rules = rules

    def _remap_wizard_button_clicked(self, _evt):
        self._open_remap_wizard()

    def _open_remap_wizard(self) -> int:
        _, preview = self._build_preview()
        dialog = _RemapWizardDialog(self, preview)
        try:
            if dialog.ShowModal() != wx.ID_OK:
                return 0
            changed_count = dialog.changed_count
        finally:
            dialog.Destroy()

        if changed_count:
            wx.MessageBox(
                f"Updated {changed_count} remap setting(s).",
                "Remap Table Updated",
                wx.OK | wx.ICON_INFORMATION,
            )
        return changed_count

    def _confirm_pre_export_preview(self) -> bool:
        rules, preview = self._build_preview()
        if preview.custom_block_total <= 0:
            self._prepared_remap_rules = rules
            return True

        while True:
            dialog = _RemapPreviewDialog(
                self,
                preview,
                title=self._remap_confirm_title(),
                allow_confirm=True,
                primary_action_label=self._remap_primary_action_label(),
                secondary_action_label=self._remap_secondary_action_label(),
                close_label="Cancel",
            )
            try:
                result = dialog.ShowModal()
            finally:
                dialog.Destroy()

            if result == wx.ID_YES:
                self._prepared_remap_rules = rules
                return True
            if result == wx.ID_NO:
                self._open_remap_wizard()
                rules, preview = self._build_preview()
                continue
            self._prepared_remap_rules = None
            return False

    def _consume_prepared_remap_rules(self, dimension, selection) -> ExportBlockRemapRules:
        rules = self._prepared_remap_rules
        self._prepared_remap_rules = None
        if rules is not None:
            return rules
        return build_export_remap_table_for_selection(self.world, dimension, selection)


# Helper module only; keep plugin autoloader quiet by exposing an empty export list.
export = []
