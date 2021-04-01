from PyQt5.QtWidgets import QAction, QComboBox, QListWidget, QWidget
from PyQt5.QtWidgets import QLineEdit
from PyQt5.QtWidgets import QCheckBox
from PyQt5.QtWidgets import QRadioButton
from PyQt5.QtWidgets import QSpinBox
from PyQt5.QtWidgets import QDoubleSpinBox
from PyQt5.QtWidgets import QGroupBox
import inspect
from PyQt5 import QtCore
from PyQt5 import QtWidgets
# ? Has to be manually defined for each widget, unfortunately


def guisave(self, settings, objects_to_exclude=None):
    """Saves GUI values to a QSettings file (.ini format)"""
    try:
        childrens = self.findChildren(QtWidgets.QWidget)
        for children in childrens:
            if isinstance(children, QtWidgets.QListWidget
                          ) and children.objectName() not in objects_to_exclude:
                settings.beginGroup(children.objectName())
                items = QtCore.QByteArray()
                stream = QtCore.QDataStream(items, QtCore.QIODevice.WriteOnly)
                for i in range(children.count()):
                    stream << children.item(i)
                selecteditems = QtCore.QByteArray()
                stream = QtCore.QDataStream(selecteditems, QtCore.QIODevice.WriteOnly)
                for it in children.selectedItems():
                    stream.writeInt(children.row(it))
                settings.setValue("items", items)
                settings.setValue("selecteditems", selecteditems)
                settings.setValue("selectionMode", children.selectionMode())
                settings.endGroup()
    except:
        pass

    for name, obj in inspect.getmembers(self):
        if isinstance(obj, QWidget) and obj.objectName() not in objects_to_exclude:
            if isinstance(obj, QComboBox):
                name = obj.objectName()
                index = obj.currentIndex()
                text = obj.itemText(index)
                settings.setValue(name, text)

            if isinstance(obj, QAction):
                if obj.isCheckable():
                    name = obj.objectName()
                    state = obj.isChecked()
                    settings.setValue(name, state)

            if isinstance(obj, QLineEdit):
                name = obj.objectName()
                value = obj.text()
                settings.setValue(name, value)

            if isinstance(obj, QCheckBox):
                name = obj.objectName()
                state = obj.checkState()
                settings.setValue(name, state)

            if isinstance(obj, QRadioButton):
                name = obj.objectName()
                state = obj.isChecked()
                settings.setValue(name, state)

            if isinstance(obj, QSpinBox):
                name = obj.objectName()
                value = obj.text()
                settings.setValue(name, int(value))

            if isinstance(obj, QDoubleSpinBox):
                name = obj.objectName()
                value = obj.text()
                settings.setValue(name, float(value.replace(",", ".")))

            if isinstance(obj, QGroupBox):
                name = obj.objectName()
                state = obj.isChecked()
                settings.setValue(name, state)
    settings.sync()


def guirestore(self, settings):
    """Restores GUI values from a QSettings file (.ini format)"""
    try:
        childrens = self.findChildren(QtWidgets.QWidget)
        for children in childrens:
            if isinstance(children, QtWidgets.QListWidget) and children.objectName():
                settings.beginGroup(children.objectName())
                items = settings.value("items")
                selecteditems = settings.value("selecteditems")
                selectionMode = settings.value(
                    "selectionMode", type=QtWidgets.QAbstractItemView.SelectionMode
                )
                children.setSelectionMode(selectionMode)
                # In the first reading the initial values must be established
                if items is None:
                    if children.objectName() == "abfdgvre":
                        for i in range(10):
                            children.addItem(QtWidgets.QListWidgetItem(str(i)))
                    elif children.objectName() == "fersgsehy":
                        for i in "abcdefghijklmnopqrstuvwxyz":
                            children.addItem(QtWidgets.QListWidgetItem(i))
                else:
                    stream = QtCore.QDataStream(items, QtCore.QIODevice.ReadOnly)
                    while not stream.atEnd():
                        it = QtWidgets.QListWidgetItem()
                        stream >> it
                        children.addItem(it)
                    stream = QtCore.QDataStream(selecteditems, QtCore.QIODevice.ReadOnly)
                    while not stream.atEnd():
                        row = stream.readInt()
                        it = children.item(row)
                        it.setSelected(True)
                settings.endGroup()
    except:
        pass
    for name, obj in inspect.getmembers(self):

        if isinstance(obj, QComboBox):
            try:
                name = obj.objectName()
                value = str(settings.value(name))
                if value in ["", "None"]:
                    continue
                # Restore the index associated to the string
                index = obj.findText(value)
                # OPTIONAL add to list if not found
                if index == -1:
                    obj.insertItems(0, [value])
                    index = obj.findText(value)
                obj.setCurrentIndex(index)
            except:
                pass

        if isinstance(obj, QLineEdit):
            try:
                name = obj.objectName()
                value = str(settings.value(name))
                if value != "None":
                    obj.setText(value)
            except:
                pass

        if isinstance(obj, QCheckBox):
            try:
                name = obj.objectName()
                value = bool(int(settings.value(name)))
                if value:
                    obj.setChecked(True)
                else:
                    obj.setChecked(False)
            except:
                pass

        if isinstance(obj, QRadioButton):
            try:
                name = obj.objectName()
                value = bool(int(settings.value(name)))
                if bool(value):
                    obj.setChecked(True)
                else:
                    obj.setChecked(False)
            except:
                pass

        if isinstance(obj, QSpinBox):
            try:
                name = obj.objectName()
                value = settings.value(name)
                if value != "None":
                    obj.setValue(int(value))

            except:
                pass

        if isinstance(obj, QDoubleSpinBox):
            try:
                name = obj.objectName()
                value = settings.value(name)
                if value != "None":
                    obj.setValue(float(value.replace(",", ".")))
            except:
                pass

        if isinstance(obj, QGroupBox):
            try:
                name = obj.objectName()
                state = str(settings.value(name))
                if state == 'true':
                    obj.setChecked(True)
                else:
                    obj.setChecked(False)
            except:
                pass


def grab_GC(window, settings):
    """Creates a global dictionary from the values 
    stored in the given QSettings file (.ini format)"""
    GC = {}
    for name, obj in inspect.getmembers(window):

        if isinstance(obj, QLineEdit):
            name = obj.objectName()
            value = str(settings.value(name))
            GC[name] = value

        if isinstance(obj, QCheckBox):
            name = obj.objectName()
            value = settings.value(name)
            GC[name] = bool(value)

        if isinstance(obj, QRadioButton):
            name = obj.objectName()
            value = settings.value(name)
            GC[name] = bool(value)

        if isinstance(obj, QSpinBox):
            name = obj.objectName()
            value = settings.value(name)
            GC[name] = int(value)

        if isinstance(obj, QDoubleSpinBox):
            name = obj.objectName()
            value = settings.value(name)
            GC[name] = float(value)

        if isinstance(obj, QGroupBox):
            name = obj.objectName()
            value = bool(settings.value(name))
            GC[name] = value
    return GC