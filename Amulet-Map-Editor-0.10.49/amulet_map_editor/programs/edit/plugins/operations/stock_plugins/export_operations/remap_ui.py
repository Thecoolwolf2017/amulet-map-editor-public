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


def _format_preview_text(preview: ExportRemapPreview, max_entries: int = 12) -> str:
    unchanged_blocks = preview.custom_block_total - preview.remapped_block_total
    lines = [
        f"Chunks scanned: {preview.scanned_chunks}/{preview.total_chunks}",
        f"Chunk read failures: {preview.failed_chunks}",
        f"Custom namespaces found: {preview.custom_namespace_count}",
        f"Custom block ids found: {preview.custom_block_count}",
        f"Custom placed blocks in selection: {preview.custom_block_total:,}",
        f"Blocks that will be remapped on export: {preview.remapped_block_total:,}",
        f"Blocks kept unchanged: {unchanged_blocks:,}",
        f"Remap enabled: {'Yes' if preview.remap_enabled else 'No'}",
        f"Auto remap for new custom blocks: {'Yes' if preview.auto_block_remap else 'No'}",
        f"Remap table path: {preview.rules_path}",
    ]
    if preview.entries:
        lines.append("")
        lines.append("Top remap entries:")
        for entry in preview.entries[:max_entries]:
            lines.append(
                f"- {entry.block_count:,}x {entry.source_block} -> {entry.replacement_block}"
            )
        hidden_entries = len(preview.entries) - max_entries
        if hidden_entries > 0:
            lines.append(f"... and {hidden_entries} more entries.")
    else:
        lines.append("")
        lines.append("No custom blocks were found in the current selection.")
    return "\n".join(lines)


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

    def _preview_remap_button_clicked(self, _evt):
        rules, preview = self._build_preview()
        text = _format_preview_text(preview)
        wx.MessageBox(text, "Export Remap Preview", wx.OK | wx.ICON_INFORMATION)
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
            message = (
                _format_preview_text(preview)
                + "\n\nExport with these mappings?\n"
                + "Yes = Export, No = Open Remap Wizard, Cancel = Stop"
            )
            dialog = wx.MessageDialog(
                self,
                message,
                "Confirm Export Remap",
                style=wx.YES_NO | wx.CANCEL | wx.CANCEL_DEFAULT | wx.ICON_QUESTION,
            )
            if hasattr(dialog, "SetYesNoCancelLabels"):
                dialog.SetYesNoCancelLabels("Export", "Remap Wizard", "Cancel")
            result = dialog.ShowModal()
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
