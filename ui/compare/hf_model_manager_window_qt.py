from __future__ import annotations

import os
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QTabWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from extensions.hf_hub_api import HfHubApiBackend
from image.image_classifier_manager import image_classifier_manager
from lib.multi_display_qt import SmartDialog
from utils.config import config
from utils.constants import HfHubSortDirection, HfHubSortOption, HfHubVisualMediaTask
from utils.logging_setup import get_logger
from utils.translations import I18N

_ = I18N._
logger = get_logger("hf_model_manager_window_qt")


class _TextPreviewDialog(SmartDialog):
    def __init__(self, parent: QWidget, title: str, text: str):
        super().__init__(parent=parent, position_parent=parent, title=title, geometry="950x700")
        layout = QVBoxLayout(self)
        self._text = QPlainTextEdit()
        self._text.setReadOnly(True)
        self._text.setPlainText(text)
        layout.addWidget(self._text)
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        close_btn = QPushButton(_("Close"))
        close_btn.clicked.connect(self.close)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)


class _SearchResultTreeItem(QTreeWidgetItem):
    """Tree item with numeric-aware sorting for downloads/likes columns."""

    NUMERIC_COLUMNS = {2, 3}

    def __lt__(self, other):
        tree = self.treeWidget()
        if tree is None:
            return super().__lt__(other)
        col = tree.sortColumn()
        if col in self.NUMERIC_COLUMNS:
            return self._int_for_col(col) < other._int_for_col(col)
        return super().__lt__(other)

    def _int_for_col(self, col: int) -> int:
        user_data = self.data(col, Qt.ItemDataRole.UserRole)
        if user_data is not None:
            try:
                return int(user_data)
            except Exception:
                pass
        try:
            return int((self.text(col) or "0").replace(",", ""))
        except Exception:
            return 0


class HfModelManagerWindow(SmartDialog):
    """Manage image classifier models from HF Hub and local config."""

    _instance: Optional["HfModelManagerWindow"] = None
    _MODEL_FILE_EXTENSIONS = {
        ".safetensors",
        ".ckpt",
        ".bin",
        ".onnx",
        ".pt",
        ".pth",
        ".h5",
        ".keras",
    }

    def __init__(self, parent: QWidget, app_actions):
        super().__init__(
            parent=parent,
            position_parent=parent,
            title=_("HF Hub Model Manager"),
            geometry="1100x700",
        )
        HfModelManagerWindow._instance = self
        self._app_actions = app_actions
        self._hf_api: Optional[HfHubApiBackend] = None
        self._repo_files_cache: dict[str, list[str]] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        self._tabs = QTabWidget()
        root.addWidget(self._tabs)

        search_page = QWidget()
        installed_page = QWidget()
        self._tabs.addTab(search_page, _("HF Hub Search"))
        self._tabs.addTab(installed_page, _("Installed Models"))

        self._build_search_tab(search_page)
        self._build_installed_tab(installed_page)
        self._refresh_installed_models()

        QShortcut(QKeySequence(Qt.Key_Escape), self).activated.connect(self.close)

    @classmethod
    def show_window(cls, parent: QWidget, app_actions):
        if cls._instance is not None:
            try:
                if cls._instance.isVisible():
                    cls._instance.raise_()
                    cls._instance.activateWindow()
                    return
            except Exception:
                cls._instance = None
        win = cls(parent, app_actions)
        win.show()

    def closeEvent(self, event):  # noqa: N802
        HfModelManagerWindow._instance = None
        super().closeEvent(event)

    def _build_search_tab(self, page: QWidget) -> None:
        layout = QVBoxLayout(page)

        # Query and ordering controls
        query_row = QHBoxLayout()
        query_row.addWidget(QLabel(_("Search")))
        self._query_edit = QLineEdit()
        self._query_edit.setPlaceholderText(_("e.g. nsfw, classifier, coherence"))
        self._query_edit.returnPressed.connect(self._search)
        query_row.addWidget(self._query_edit, stretch=1)

        query_row.addWidget(QLabel(_("Task")))
        self._task_combo = QComboBox()
        for task in HfHubVisualMediaTask:
            self._task_combo.addItem(task.display(), task.value)
        self._task_combo.setCurrentText(HfHubVisualMediaTask.IMAGE_CLASSIFICATION.display())
        query_row.addWidget(self._task_combo)

        query_row.addWidget(QLabel(_("Sort")))
        self._sort_combo = QComboBox()
        for sort_option in HfHubSortOption:
            self._sort_combo.addItem(sort_option.display(), sort_option.value)
        self._sort_combo.setCurrentText(HfHubSortOption.DOWNLOADS.display())
        query_row.addWidget(self._sort_combo)

        query_row.addWidget(QLabel(_("Direction")))
        self._direction_combo = QComboBox()
        for direction in HfHubSortDirection:
            self._direction_combo.addItem(direction.display(), direction.value)
        self._direction_combo.setCurrentText(HfHubSortDirection.DESCENDING.display())
        query_row.addWidget(self._direction_combo)

        query_row.addWidget(QLabel(_("Limit")))
        self._limit_combo = QComboBox()
        for value in ("25", "50", "100", "200"):
            self._limit_combo.addItem(value)
        self._limit_combo.setCurrentText("100")
        query_row.addWidget(self._limit_combo)

        self._include_gated_cb = QCheckBox(_("Include gated"))
        self._include_gated_cb.setChecked(True)
        query_row.addWidget(self._include_gated_cb)

        search_btn = QPushButton(_("Search"))
        search_btn.clicked.connect(self._search)
        query_row.addWidget(search_btn)
        layout.addLayout(query_row)

        # Search results
        self._search_tree = QTreeWidget()
        self._search_tree.setHeaderLabels(
            [_("Repo"), _("Task"), _("Downloads"), _("Likes"), _("License"), _("Gated")]
        )
        self._search_tree.setRootIsDecorated(False)
        self._search_tree.setAlternatingRowColors(True)
        self._search_tree.setSortingEnabled(True)
        self._search_tree.itemSelectionChanged.connect(self._on_repo_selection_changed)
        hdr = self._search_tree.header()
        hdr.setStretchLastSection(True)
        self._search_tree.sortByColumn(2, Qt.SortOrder.DescendingOrder)
        layout.addWidget(self._search_tree)

        # Download + install controls
        install_row_1 = QHBoxLayout()
        install_row_1.addWidget(QLabel(_("Model file")))
        self._filename_combo = QComboBox()
        self._filename_combo.setEditable(True)
        self._filename_combo.addItem("model.safetensors")
        install_row_1.addWidget(self._filename_combo, stretch=1)
        load_files_btn = QPushButton(_("Load Repo Files"))
        load_files_btn.clicked.connect(self._load_selected_repo_files)
        install_row_1.addWidget(load_files_btn)
        card_btn = QPushButton(_("View Model Card"))
        card_btn.clicked.connect(self._view_model_card)
        install_row_1.addWidget(card_btn)
        dl_btn = QPushButton(_("Download and Install"))
        dl_btn.clicked.connect(self._download_and_install_selected)
        install_row_1.addWidget(dl_btn)
        layout.addLayout(install_row_1)

        install_row_2 = QHBoxLayout()
        install_row_2.addWidget(QLabel(_("Model name")))
        self._model_name_edit = QLineEdit()
        install_row_2.addWidget(self._model_name_edit, stretch=1)
        install_row_2.addWidget(QLabel(_("Categories")))
        self._categories_edit = QLineEdit("positive,negative")
        self._categories_edit.setPlaceholderText(_("Comma-separated categories"))
        install_row_2.addWidget(self._categories_edit, stretch=1)
        install_row_2.addWidget(QLabel(_("Backend")))
        self._backend_combo = QComboBox()
        self._backend_combo.addItems(["auto", "pytorch", "hdf5"])
        install_row_2.addWidget(self._backend_combo)
        layout.addLayout(install_row_2)

        install_row_3 = QHBoxLayout()
        self._use_transformers_auto_model_cb = QCheckBox(_("Use Transformers AutoModel"))
        self._use_transformers_auto_model_cb.setToolTip(
            _("Recommended for HF model repos with config.json and processor files.")
        )
        self._use_transformers_auto_model_cb.setChecked(True)
        install_row_3.addWidget(self._use_transformers_auto_model_cb)

        install_row_3.addWidget(QLabel(_("Arch module")))
        self._arch_module_edit = QLineEdit()
        self._arch_module_edit.setPlaceholderText("architecture_module_name")
        install_row_3.addWidget(self._arch_module_edit, stretch=1)

        install_row_3.addWidget(QLabel(_("Arch class")))
        self._arch_class_edit = QLineEdit()
        self._arch_class_edit.setPlaceholderText("architecture_class_path (optional)")
        install_row_3.addWidget(self._arch_class_edit, stretch=1)
        layout.addLayout(install_row_3)

    def _build_installed_tab(self, page: QWidget) -> None:
        layout = QVBoxLayout(page)

        self._installed_tree = QTreeWidget()
        self._installed_tree.setHeaderLabels(
            [_("Model Name"), _("Backend"), _("Categories"), _("Model Location")]
        )
        self._installed_tree.setRootIsDecorated(False)
        self._installed_tree.setAlternatingRowColors(True)
        self._installed_tree.setSortingEnabled(True)
        hdr = self._installed_tree.header()
        hdr.setStretchLastSection(True)
        layout.addWidget(self._installed_tree)

        btn_row = QHBoxLayout()
        refresh_btn = QPushButton(_("Refresh"))
        refresh_btn.clicked.connect(self._refresh_installed_models)
        btn_row.addWidget(refresh_btn)

        remove_btn = QPushButton(_("Remove Selected"))
        remove_btn.clicked.connect(self._remove_selected_installed_model)
        btn_row.addWidget(remove_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

    def _api(self) -> HfHubApiBackend:
        if self._hf_api is None:
            self._hf_api = HfHubApiBackend()
        return self._hf_api

    def _selected_repo(self) -> Optional[str]:
        selected = self._search_tree.selectedItems()
        if not selected:
            self._app_actions.warn(_("Please select a model repository first."))
            return None
        return selected[0].text(0)

    def _selected_repo_silent(self) -> Optional[str]:
        selected = self._search_tree.selectedItems()
        if not selected:
            return None
        return selected[0].text(0)

    def _search(self) -> None:
        try:
            query = (self._query_edit.text() or "").strip()
            task = HfHubVisualMediaTask.get(str(self._task_combo.currentData()))
            sort = HfHubSortOption.get(str(self._sort_combo.currentData()))
            direction = HfHubSortDirection.get(str(self._direction_combo.currentData()))
            limit = int(self._limit_combo.currentText())

            results = self._api().search_models(
                query=query,
                task=task,
                limit=limit,
                sort=sort,
                direction=direction,
                include_gated=self._include_gated_cb.isChecked(),
            )
            self._search_tree.setSortingEnabled(False)
            self._search_tree.clear()
            for r in results:
                item = _SearchResultTreeItem(
                    [
                        r.repo_id,
                        r.task or "",
                        str(r.downloads),
                        str(r.likes),
                        r.license,
                        _("yes") if r.gated else _("no"),
                    ]
                )
                item.setData(2, Qt.ItemDataRole.UserRole, int(r.downloads))
                item.setData(3, Qt.ItemDataRole.UserRole, int(r.likes))
                self._search_tree.addTopLevelItem(item)
            self._search_tree.setSortingEnabled(True)
            self._apply_search_tree_sort(sort, direction)
            if self._search_tree.topLevelItemCount() > 0:
                self._search_tree.setCurrentItem(self._search_tree.topLevelItem(0))
            self._app_actions.toast(_("Found {0} results").format(len(results)))
        except Exception as e:
            logger.error(f"HF Hub search failed: {e}")
            self._app_actions.alert(_("HF Hub Search Error"), str(e), kind="error", master=self)

    def _apply_search_tree_sort(
        self,
        sort: HfHubSortOption,
        direction: HfHubSortDirection,
    ) -> None:
        """Apply visible-table sorting to match selected sort controls where possible."""
        sort_col_map = {
            HfHubSortOption.DOWNLOADS: 2,
            HfHubSortOption.LIKES: 3,
        }
        col = sort_col_map.get(sort)
        if col is None:
            return
        order = (
            Qt.SortOrder.DescendingOrder
            if direction == HfHubSortDirection.DESCENDING
            else Qt.SortOrder.AscendingOrder
        )
        self._search_tree.sortByColumn(col, order)

    def _on_repo_selection_changed(self) -> None:
        repo_id = self._selected_repo_silent()
        if not repo_id:
            return
        self._model_name_edit.setText(self._default_model_name(repo_id))
        self._set_repo_file_options(repo_id)
        self._use_transformers_auto_model_cb.setChecked(
            self._guess_transformers_auto_model_default(repo_id)
        )

    def _set_repo_file_options(self, repo_id: str) -> None:
        try:
            if repo_id in self._repo_files_cache:
                files = self._repo_files_cache[repo_id]
            else:
                files = self._api().list_model_files(repo_id)
                self._repo_files_cache[repo_id] = files
            preferred = [f for f in files if os.path.splitext(f)[1].lower() in self._MODEL_FILE_EXTENSIONS]
            values = preferred if preferred else files
            current = self._filename_combo.currentText().strip()
            self._filename_combo.clear()
            for value in values:
                self._filename_combo.addItem(value)
            if current and current in values:
                self._filename_combo.setCurrentText(current)
            elif values:
                self._filename_combo.setCurrentText(values[0])
            elif current:
                self._filename_combo.setEditText(current)
            else:
                self._filename_combo.setEditText("model.safetensors")
        except Exception as e:
            logger.error(f"Failed to load repo file list for {repo_id}: {e}")

    def _guess_transformers_auto_model_default(self, repo_id: str) -> bool:
        files = self._repo_files_cache.get(repo_id, [])
        if not files:
            return False
        lower = {f.lower() for f in files}
        has_config = "config.json" in lower
        has_processor = (
            "preprocessor_config.json" in lower
            or "processor_config.json" in lower
            or "feature_extractor_config.json" in lower
        )
        has_model_weights = any(
            os.path.splitext(f)[1].lower() in self._MODEL_FILE_EXTENSIONS
            for f in files
        )
        return has_config and has_model_weights and has_processor

    def _load_selected_repo_files(self) -> None:
        repo_id = self._selected_repo()
        if repo_id is None:
            return
        self._set_repo_file_options(repo_id)
        self._app_actions.toast(_("Loaded repo files for {0}.").format(repo_id))

    def _view_model_card(self) -> None:
        repo_id = self._selected_repo()
        if repo_id is None:
            return
        try:
            card_text = self._api().get_model_card_text(repo_id)
            _TextPreviewDialog(
                parent=self,
                title=_("Model Card - {0}").format(repo_id),
                text=card_text,
            ).show()
        except Exception as e:
            logger.error(f"Failed to fetch model card for {repo_id}: {e}")
            self._app_actions.alert(_("Model Card Error"), str(e), kind="error", master=self)

    def _download_and_install_selected(self) -> None:
        repo_id = self._selected_repo()
        if repo_id is None:
            return
        filename = (self._filename_combo.currentText() or "").strip()
        if not filename:
            self._app_actions.warn(_("Please enter a filename to download."))
            return

        try:
            snapshot_dir = self._api().download_snapshot(repo_id)
            downloaded_path = self._resolve_downloaded_file_path(snapshot_dir, filename)
            if downloaded_path is None:
                raise RuntimeError(_("Unable to locate selected file in downloaded snapshot: {0}").format(filename))
        except Exception as e:
            logger.error(f"HF Hub download failed: {e}")
            self._app_actions.alert(_("HF Hub Download Error"), str(e), kind="error", master=self)
            return

        default_name = self._default_model_name(repo_id)
        model_name = (self._model_name_edit.text() or default_name).strip()
        if not model_name:
            self._app_actions.warn(_("Model name must not be empty."))
            return

        categories_text = (self._categories_edit.text() or "").strip()
        categories = [c.strip() for c in categories_text.split(",") if c.strip()]
        if not categories:
            self._app_actions.warn(_("Please enter at least one category."))
            return

        backend = str(self._backend_combo.currentText()).strip().lower()
        use_transformers_auto_model = self._use_transformers_auto_model_cb.isChecked()
        model_kwargs = {}
        if use_transformers_auto_model:
            model_kwargs["use_transformers_auto_model"] = True
            model_kwargs["hf_pretrained_path"] = snapshot_dir
        arch_module = (self._arch_module_edit.text() or "").strip()
        arch_class = (self._arch_class_edit.text() or "").strip()
        if arch_module:
            model_kwargs["architecture_module_name"] = arch_module
        if arch_class:
            model_kwargs["architecture_class_path"] = arch_class

        effective_backend = "pytorch" if use_transformers_auto_model else (backend if backend else "auto")
        model_details = {
            "model_name": model_name,
            "model_location": downloaded_path,
            "model_categories": categories,
            "backend": effective_backend,
        }
        if model_kwargs:
            model_details["model_kwargs"] = model_kwargs

        existing_names = {m.get("model_name") for m in config.image_classifier_models}
        if model_name in existing_names:
            should_replace = self._app_actions.alert(
                _("Replace Existing Model?"),
                _("A model named '{0}' already exists. Replace it?").format(model_name),
                kind="askokcancel",
                master=self,
            )
            if not should_replace:
                return

        updated_models = []
        replaced = False
        for existing in config.image_classifier_models:
            if existing.get("model_name") == model_name:
                updated_models.append(model_details)
                replaced = True
            else:
                updated_models.append(existing)
        if not replaced:
            updated_models.append(model_details)

        try:
            config.set_image_classifier_models(updated_models)
            image_classifier_manager.set_classifier_metadata(config.image_classifier_models)
        except Exception as e:
            logger.error(f"Failed to persist model details: {e}")
            self._app_actions.alert(_("Config Update Error"), str(e), kind="error", master=self)
            return

        self._refresh_installed_models()
        self._tabs.setCurrentIndex(1)
        self._model_name_edit.setText(model_name)
        self._app_actions.success(
            _("Downloaded and installed model '{0}'.").format(model_name)
        )

    @staticmethod
    def _default_model_name(repo_id: str) -> str:
        repo = (repo_id or "").strip()
        return repo if repo else "hf_model"

    @staticmethod
    def _resolve_downloaded_file_path(snapshot_dir: str, selected_filename: str) -> Optional[str]:
        normalized = selected_filename.replace("/", os.sep)
        expected = os.path.join(snapshot_dir, normalized)
        if os.path.isfile(expected):
            return expected

        # Fallback: resolve by basename when file path structure differs.
        basename = os.path.basename(normalized)
        if not basename:
            return None
        for root, _, files in os.walk(snapshot_dir):
            if basename in files:
                return os.path.join(root, basename)
        return None

    def _refresh_installed_models(self) -> None:
        self._installed_tree.clear()
        for model in list(config.image_classifier_models):
            categories = model.get("model_categories") or []
            categories_text = ", ".join(str(c) for c in categories)
            backend = str(model.get("backend", "auto"))
            QTreeWidgetItem(
                self._installed_tree,
                [
                    str(model.get("model_name", "")),
                    backend,
                    categories_text,
                    str(model.get("model_location", "")),
                ],
            )

    def _remove_selected_installed_model(self) -> None:
        selected = self._installed_tree.selectedItems()
        if not selected:
            self._app_actions.warn(_("Please select an installed model first."))
            return
        model_name = selected[0].text(0)
        should_remove = self._app_actions.alert(
            _("Remove Installed Model?"),
            _("Remove '{0}' from configured image classifier models?").format(model_name),
            kind="askokcancel",
            master=self,
        )
        if not should_remove:
            return

        updated_models = [
            m for m in config.image_classifier_models
            if m.get("model_name") != model_name
        ]
        if len(updated_models) == len(config.image_classifier_models):
            self._app_actions.warn(_("No matching model named '{0}' was found.").format(model_name))
            return

        try:
            config.set_image_classifier_models(updated_models)
            image_classifier_manager.set_classifier_metadata(config.image_classifier_models)
        except Exception as e:
            logger.error(f"Failed to remove model details: {e}")
            self._app_actions.alert(_("Config Update Error"), str(e), kind="error", master=self)
            return

        self._refresh_installed_models()
        self._app_actions.success(_("Removed model '{0}'.").format(model_name))
