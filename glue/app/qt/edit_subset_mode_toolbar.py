from __future__ import absolute_import, division, print_function

from qtpy import QtCore, QtWidgets
from glue.core.edit_subset_mode import (OrMode,
                                        AndNotMode, AndMode, XorMode,
                                        ReplaceMode)
from glue.app.qt.actions import action
from glue.utils import nonpartial, avoid_circular
from glue.utils.qt import update_combobox
from glue.core.message import EditSubsetMessage, SubsetMessage
from glue.core.hub import HubListener
from glue.external.six import string_types
from glue.icons.qt import layer_icon


class EditSubsetModeToolBar(QtWidgets.QToolBar, HubListener):

    def __init__(self, title="Subset Update Mode", parent=None):
        super(EditSubsetModeToolBar, self).__init__(title, parent)

        self.subset_combo = QtWidgets.QComboBox()

        spacer = QtWidgets.QWidget()
        spacer.setMinimumSize(10, 10)
        spacer.setSizePolicy(QtWidgets.QSizePolicy.Fixed,
                             QtWidgets.QSizePolicy.Preferred)

        self.addWidget(spacer)
        self.addWidget(QtWidgets.QLabel("Active Subset:"))
        self.addWidget(self.subset_combo)

        self.addWidget(QtWidgets.QLabel("Subset Mode:"))
        self.setIconSize(QtCore.QSize(20, 20))
        self._group = QtWidgets.QActionGroup(self)
        self._modes = {}
        self._add_actions()
        self._edit_subset_mode = self.parent()._session.edit_subset_mode
        self._modes[self._edit_subset_mode.mode].trigger()
        self._backup_mode = None

        spacer = QtWidgets.QWidget()
        spacer.setMinimumSize(20, 10)
        spacer.setSizePolicy(QtWidgets.QSizePolicy.Fixed,
                             QtWidgets.QSizePolicy.Preferred)

        self.addWidget(spacer)

        self.parent()._hub.subscribe(self, EditSubsetMessage, handler=self._update_mode)
        self.parent()._hub.subscribe(self, SubsetMessage, handler=self._update_subset_combo)

        self._data_collection = self.parent().data_collection
        self._update_subset_combo()
        self.subset_combo.currentIndexChanged.connect(self._on_subset_combo_change)

    def _update_subset_combo(self, msg=None):
        """
        Set up the combo listing the subsets.
        """

        # Prepare contents of combo box - we include a 'Create subset' item as
        # the last item
        labeldata = [(subset.label, subset) for subset in self._data_collection.subset_groups]
        labeldata.append(('Create subset', None))

        # We now update the combo box, but we block the signals as we don't want
        # this to cause the current subset being edited to be modified.

        self.subset_combo.blockSignals(True)

        # The block_signals here is to prevent signals from being turned back
        # on inside update_combobox.
        update_combobox(self.subset_combo, labeldata, block_signals=False)
        self.subset_combo.setIconSize(QtCore.QSize(12, 12))
        for index, subset in enumerate(self._data_collection.subset_groups):
            self.subset_combo.setItemIcon(index, layer_icon(subset))

        # We now pretend that the EditSubsetMode has change to force the current
        # combo selection to be in sync.
        self._on_edit_subset_mode_change()

        self.subset_combo.blockSignals(False)

    @avoid_circular
    def _on_subset_combo_change(self, event=None):
        """
        Update the EditSubsetMode when the subset combo changes.
        """

        subset = self.subset_combo.currentData()

        if subset is None:
            self._edit_subset_mode.edit_subset = []
        else:
            self._edit_subset_mode.edit_subset = [self.subset_combo.currentData()]

        # We now force the combo to be refreshed in case it included the
        # temporary 'Multiple subsets' entry which needs to be removed.
        self.subset_combo.blockSignals(True)
        self._update_subset_combo()
        self.subset_combo.blockSignals(False)

    @avoid_circular
    def _on_edit_subset_mode_change(self):
        """
        Update the subset combo when the EditSubsetMode changes.
        """

        # We block signals since we don't want to trigger a change in EditSubsetMode.

        self.subset_combo.blockSignals(True)

        edit_subset = self._edit_subset_mode.edit_subset

        if len(edit_subset) > 1:
            # We temporarily add an item - we remove this if the combo changes
            # again.
            self.subset_combo.insertItem(0, 'Multiple subsets')
            index = 0
        else:
            self._update_subset_combo()
            if edit_subset:
                index = self._data_collection.subset_groups.index(edit_subset[0])
            elif len(edit_subset) == 0:
                index = self.subset_combo.count() - 1

        self.subset_combo.setCurrentIndex(index)
        self.subset_combo.blockSignals(False)

    def _make_mode(self, name, tip, icon, mode):

        def set_mode(mode):
            self._edit_subset_mode.mode = mode

        a = action(name, self, tip, icon)
        a.setCheckable(True)
        a.triggered.connect(nonpartial(set_mode, mode))
        self._group.addAction(a)
        self.addAction(a)
        self._modes[mode] = a
        label = name.split()[0].lower().replace('&', '')
        self._modes[label] = mode

    def _add_actions(self):
        self._make_mode("&Replace Mode", "Replace selection",
                        'glue_replace', ReplaceMode)
        self._make_mode("&Or Mode", "Add to selection",
                        'glue_or', OrMode)
        self._make_mode("&And Mode", "Set selection as intersection",
                        'glue_and', AndMode)
        self._make_mode("&Xor Mode", "Set selection as exclusive intersection",
                        'glue_xor', XorMode)
        self._make_mode("&Not Mode", "Remove from selection",
                        'glue_andnot', AndNotMode)

    def _update_mode(self, message):
        self.set_mode(message.mode)
        self._on_edit_subset_mode_change()

    def set_mode(self, mode):
        """Temporarily set the edit mode to mode
        :param mode: Name of the mode (Or, Not, And, Xor, Replace)
        :type mode: str
        """
        if isinstance(mode, string_types):
            try:
                mode = self._modes[mode]  # label to mode class
            except KeyError:
                raise KeyError("Unrecognized mode: %s" % mode)

        self._backup_mode = self._backup_mode or self._edit_subset_mode.mode
        self._modes[mode].trigger()  # mode class to action

    def unset_mode(self):
        """Restore the mode to the state before set_mode was called"""
        mode = self._backup_mode
        self._backup_mode = None
        if mode:
            self._modes[mode].trigger()
