from pathlib import Path

target_file = Path(r"e:\Users\james\Documents\Code\MusicalScumme_v2.2.0\musical_scumme\ui.py")
content = target_file.read_text(encoding="utf-8")

# 1. Update imports
old_import = "from .planner import build_playback_plan, export_plan_csv, export_score_csv"
new_import = "from .planner import build_playback_plan, export_plan_csv, export_score_csv, recommend_optimal_transpose"
assert old_import in content, "planner import not found in ui.py"
content = content.replace(old_import, new_import, 1)

# 2. Add MappingComparisonDialog before MainWindow
dialog_code = '''class MappingComparisonDialog(QDialog):
    def __init__(
        self,
        notes: list[MidiNote],
        settings: AppSettings,
        parent: QWidget | None = None,
        prepared_source: bool = False,
        track_names: dict[int, str] | None = None,
    ) -> None:
        super().__init__(parent)
        _enable_translucent_frame(self)
        self.setWindowTitle("Pitch Mapping Policy Comparison")
        self.setMinimumWidth(820)
        self.selected_mode: str | None = None
        self.notes = notes
        self.settings = settings
        self.prepared_source = prepared_source
        self.track_names = track_names or {}

        layout = QVBoxLayout(self)
        layout.addWidget(_dialog_header(self, "Compare Pitch Mapping Policies"))

        summary = QLabel(
            "Side-by-side scorecard comparing note retention, octave-bank switching, "
            "and musical voice preservation across all 5 SCUM mapping policies for the active score."
        )
        summary.setWordWrap(True)
        summary.setObjectName("subtitle")
        layout.addWidget(summary)

        modes = [
            ("fold_smart", "Enhanced Fold", "Safe base-bank fold with unison C preservation"),
            ("match3_adaptive", "Enhanced Pitch Match", "Adaptive song-register shift + 3-octave coverage"),
            ("strict_auto", "Enhanced Strict", "Single whole-octave shift, omits out-of-range notes"),
            ("melody3_contour", "Enhanced Contour", "Minimizes pitch loss & interval distortion for lead"),
            ("smart3_harmonic", "Enhanced Intelligent", "Harmonic-aware bank optimization with rest discounting"),
        ]

        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(10)

        profile = settings.resolved_profile()
        for mode_key, mode_title, mode_desc in modes:
            test_settings = replace(settings, mapping_mode=mode_key)
            plan = build_playback_plan(
                notes,
                test_settings,
                profile,
                prepared_source=prepared_source,
                track_names=self.track_names,
            )

            card = QFrame()
            card.setObjectName("card")
            card_layout = QVBoxLayout(card)
            card_layout.setSpacing(6)

            title_lbl = QLabel(mode_title)
            title_lbl.setStyleSheet("font-weight: bold; font-size: 13px; color: #ffffff;")
            card_layout.addWidget(title_lbl)

            desc_lbl = QLabel(mode_desc)
            desc_lbl.setWordWrap(True)
            desc_lbl.setObjectName("muted")
            desc_lbl.setStyleSheet("font-size: 11px; min-height: 38px;")
            card_layout.addWidget(desc_lbl)

            total_source = plan.source_notes or len(notes)
            retained = plan.retained_notes
            retained_pct = (retained / total_source * 100.0) if total_source else 0.0
            bank_taps = sum(
                1 for e in plan.events if "octave bank" in e.reason and e.action == "down"
            )
            transition_delays = plan.diagnostics.get("transition_delays", 0)

            stats_form = QFormLayout()
            stats_form.setContentsMargins(0, 4, 0, 4)
            stats_form.addRow("Retained:", QLabel(f"{retained:,} / {total_source:,} ({retained_pct:.0f}%)"))
            stats_form.addRow("Dropped:", QLabel(f"{plan.dropped_total:,}"))
            stats_form.addRow("Bank taps:", QLabel(f"{bank_taps:,}"))
            stats_form.addRow("Delays:", QLabel(f"{transition_delays:,}"))
            card_layout.addLayout(stats_form)

            card_layout.addStretch(1)

            apply_btn = QPushButton(f"Apply {mode_title}")
            is_active = (mode_key == settings.mapping_mode)
            if is_active:
                apply_btn.setText("Currently Active")
                apply_btn.setEnabled(False)
            else:
                apply_btn.clicked.connect(lambda checked=False, m=mode_key: self._select_mode(m))
            card_layout.addWidget(apply_btn)

            cards_layout.addWidget(card)

        layout.addLayout(cards_layout)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.reject)
        btn_layout = QHBoxLayout()
        btn_layout.addStretch(1)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

    def _select_mode(self, mode: str) -> None:
        self.selected_mode = mode
        self.accept()


'''

assert "class MainWindow(QMainWindow):" in content, "class MainWindow not found"
content = content.replace("class MainWindow(QMainWindow):", dialog_code + "class MainWindow(QMainWindow):", 1)

# 3. Add auto_transpose_button next to transpose_spin
old_transpose_ui = """        self.transpose_spin = QSpinBox()
        self.transpose_spin.setRange(-36, 36)
        self.transpose_spin.setSuffix(" semitones")
        self.performance_form.addRow("Transpose", self.transpose_spin)"""

new_transpose_ui = """        self.transpose_spin = QSpinBox()
        self.transpose_spin.setRange(-36, 36)
        self.transpose_spin.setSuffix(" semitones")
        self.auto_transpose_button = QPushButton("Auto / Recommend")
        self.auto_transpose_button.setToolTip("Analyze current notes and automatically set the transposition that maximizes in-bank coverage.")
        self.auto_transpose_button.clicked.connect(self._recommend_transpose_clicked)
        transpose_layout = QHBoxLayout()
        transpose_layout.setContentsMargins(0, 0, 0, 0)
        transpose_layout.addWidget(self.transpose_spin, 1)
        transpose_layout.addWidget(self.auto_transpose_button)
        self.performance_form.addRow("Transpose", transpose_layout)"""

assert old_transpose_ui in content, "old_transpose_ui not found"
content = content.replace(old_transpose_ui, new_transpose_ui, 1)

# 4. Add compare_mappings_button near mapping_combo
old_mapping_ui = """        self.mapping_combo = QComboBox()
        self.mapping_combo.addItem("Enhanced Fold · fuller C chords", "fold_smart")
        self.mapping_combo.addItem("Enhanced Pitch Match · fit song register", "match3_adaptive")
        self.mapping_combo.addItem("Enhanced Strict · centre one octave", "strict_auto")
        self.mapping_combo.addItem("Enhanced Contour · preserve melody", "melody3_contour")
        self.mapping_combo.addItem("Enhanced Intelligent · balance chords", "smart3_harmonic")
        _fit_combo_to_panel(self.mapping_combo)
        mapping_form.addRow("Pitch mapping", self.mapping_combo)"""

new_mapping_ui = """        self.mapping_combo = QComboBox()
        self.mapping_combo.addItem("Enhanced Fold · fuller C chords", "fold_smart")
        self.mapping_combo.addItem("Enhanced Pitch Match · fit song register", "match3_adaptive")
        self.mapping_combo.addItem("Enhanced Strict · centre one octave", "strict_auto")
        self.mapping_combo.addItem("Enhanced Contour · preserve melody", "melody3_contour")
        self.mapping_combo.addItem("Enhanced Intelligent · balance chords", "smart3_harmonic")
        _fit_combo_to_panel(self.mapping_combo)
        self.compare_mappings_button = QPushButton("Compare Mappings…")
        self.compare_mappings_button.setToolTip("Compare note retention, octave bank shifts, and timing across all 5 SCUM pitch mapping policies.")
        self.compare_mappings_button.clicked.connect(self._open_mapping_comparison)
        mapping_row = QHBoxLayout()
        mapping_row.setContentsMargins(0, 0, 0, 0)
        mapping_row.addWidget(self.mapping_combo, 1)
        mapping_row.addWidget(self.compare_mappings_button)
        mapping_form.addRow("Pitch mapping", mapping_row)"""

assert old_mapping_ui in content, "old_mapping_ui not found"
content = content.replace(old_mapping_ui, new_mapping_ui, 1)

# 5. Connect octave keys and timing settings into scheduler.start in _start_playback
old_sched_start = """            self.scheduler.start(
                plan,
                countdown_s=countdown_s,
                require_scum_focus=require_focus,
                pause_on_focus_loss=self.settings.pause_on_focus_loss,
                repeat=repeat,
                repeat_gap_ms=self.settings.section_gap_ms,
            )"""

new_sched_start = """            self.scheduler.start(
                plan,
                countdown_s=countdown_s,
                require_scum_focus=require_focus,
                pause_on_focus_loss=self.settings.pause_on_focus_loss,
                repeat=repeat,
                repeat_gap_ms=self.settings.section_gap_ms,
                octave_up_key=self.key_profile.octave_up,
                octave_down_key=self.key_profile.octave_down,
                modifier_release_ms=self.settings.modifier_release_ms,
                modifier_settle_ms=self.settings.modifier_settle_ms,
            )"""

assert old_sched_start in content, "old_sched_start not found"
content = content.replace(old_sched_start, new_sched_start, 1)

# 6. Add _current_source_notes, _recommend_transpose_clicked, _open_mapping_comparison methods to MainWindow
methods_code = '''
    def _current_source_notes(self) -> list[MidiNote]:
        if not self.project:
            return []
        tracks = self.selected_track_indices()
        if not tracks:
            return []
        notes = self.project.notes_for_tracks(tracks)
        if self.playback_sections:
            selection = apply_playback_sections(
                notes,
                self.playback_sections,
                source_duration_ms=self.project.duration_ms,
                gap_ms=self.settings.section_gap_ms,
            )
            return list(selection.notes)
        return notes

    def _recommend_transpose_clicked(self) -> None:
        notes = self._current_source_notes()
        if not notes:
            QMessageBox.information(self, APP_TITLE, "Load a MIDI file or transcription first to analyze transposition.")
            return
        best_shift, metrics = recommend_optimal_transpose(notes, self.settings)
        self.transpose_spin.setValue(best_shift)
        self.settings.transpose = best_shift
        self._sync_state_from_controls()
        self.build_plan()
        self._set_status(
            f"Recommended transpose: {best_shift:+d} semitones · "
            f"{metrics['in_bank_pct']:.0f}% in-bank (C4–C5), {metrics['in_range_pct']:.0f}% in SCUM range"
        )

    def _open_mapping_comparison(self) -> None:
        notes = self._current_source_notes()
        if not notes:
            QMessageBox.information(
                self, APP_TITLE, "Load a MIDI file or transcription first to compare pitch mapping policies."
            )
            return
        tracks = self.selected_track_indices()
        dialog = MappingComparisonDialog(
            notes,
            self.settings,
            parent=self,
            prepared_source=_selection_is_prepared_song(self.project, tracks) if self.project else False,
            track_names={t.index: t.name for t in self.project.tracks} if self.project else {},
        )
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.selected_mode:
            self.settings.mapping_mode = dialog.selected_mode
            index = self.mapping_combo.findData(dialog.selected_mode)
            if index >= 0:
                self.mapping_combo.setCurrentIndex(index)
            self._sync_state_from_controls()
            self.build_plan()
            self._set_status(f"Applied {self.mapping_combo.currentText()}")
'''

# Insert methods before _start_playback
anchor_method = "    def _start_playback("
assert anchor_method in content, "_start_playback not found"
content = content.replace(anchor_method, methods_code + "\n" + anchor_method, 1)

target_file.write_text(content, encoding="utf-8")
print("Successfully patched ui.py")
