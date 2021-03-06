import inspect

from PyQt5 import QtCore, QtWidgets
from PyQt5.QtWidgets import (
    QAction, QCheckBox, QComboBox, QDateEdit, QDoubleSpinBox, QGroupBox, QKeySequenceEdit, QLineEdit, QListWidget, QRadioButton, QSpinBox, QWidget
)

# ? Has to be manually defined for each widget, unfortunately

#//___________________________________________________________________
#! CRUCIAL set objectNames, else QSettings::setValue: Empty key passed
#//___________________________________________________________________


def guisave(self, settings: QtCore.QSettings, objects_to_exclude=None):
    # sourcery no-metrics
    """
    Saves GUI values to a QSettings file (.ini format). \n
    ``objects_to_exclude`` : Exclude objects to save by its objectName property. 
    """
    
    print("\n\nSAVING SETTINGS \n\n")
    try:
        childrens = self.findChildren(QtWidgets.QWidget)
        for children in childrens:
            if isinstance(children, QtWidgets.QListWidget) and children.objectName() not in objects_to_exclude:
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
        try:
            if isinstance(obj, QWidget) and obj.objectName() not in objects_to_exclude:
                if isinstance(obj, QComboBox):
                    try:
                        name = obj.objectName()
                        index = obj.currentIndex()
                        text = obj.itemText(index)
                        settings.setValue(name, text)
                    except:
                        pass

                if isinstance(obj, QAction):
                    if obj.isCheckable():
                        try:
                            name = obj.objectName()
                            state = obj.isChecked()
                            settings.setValue(name, state)
                        except:
                            pass    

                if isinstance(obj, QLineEdit):
                    try:
                        name = obj.objectName()
                        value = obj.text()
                        # print(name, value, "for ", obj)
                        settings.setValue(name, value)
                    except:
                        pass   
                    
                if isinstance(obj, QCheckBox):
                    try:
                        name = obj.objectName()
                        state = obj.checkState()
                        settings.setValue(name, state)
                    except:
                        pass  
                    
                if isinstance(obj, QRadioButton):
                    try:
                        name = obj.objectName()
                        state = obj.isChecked()
                        settings.setValue(name, state)
                    except:
                        pass   
                    
                if isinstance(obj, QSpinBox):
                    try:
                        name = obj.objectName()
                        value = obj.text()
                        settings.setValue(name, int(value))
                    except:
                        pass   
                    
                if isinstance(obj, QDoubleSpinBox):
                    try:
                        name = obj.objectName()
                        value = obj.text()
                        settings.setValue(name, float(value.replace(",", ".")))
                    except:
                        pass   
                    
                if isinstance(obj, QGroupBox):
                    try:
                        name = obj.objectName()
                        state = obj.isChecked()
                        settings.setValue(name, state)
                    except:
                        pass   
                                    
                if isinstance(obj, QDateEdit):
                    try:
                        name = obj.objectName()
                        value = obj.date()
                        settings.setValue(name, value)
                    except:
                        pass   
                                    
                if isinstance(obj, QKeySequenceEdit):
                    try:
                        name = obj.objectName()
                        key = obj.keySequence()
                        settings.setValue(name, key)  
                    except:
                        pass   
        except:
            continue
                                
    settings.sync()


def guirestore(self, settings: QtCore.QSettings):  # sourcery no-metrics
    """Restores GUI values from a QSettings file (.ini format)"""
    print("\n\nRESTORING SETTINGS \n\n")
    
    try:
        childrens = self.findChildren(QtWidgets.QWidget)
        for children in childrens:
            if isinstance(children, QtWidgets.QListWidget) and children.objectName():
                settings.beginGroup(children.objectName())
                items = settings.value("items")
                selecteditems = settings.value("selecteditems")
                selectionMode = settings.value("selectionMode", type=QtWidgets.QAbstractItemView.SelectionMode)
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
        
        if isinstance(obj, QDateEdit):
            try:
                name = obj.objectName()
                value = settings.value(name)
                if value != "None":
                    obj.setDate(value)
            except:
                pass
        
        if isinstance(obj, QKeySequenceEdit):
            try:
                name = obj.objectName()
                key = str(settings.value(name))
                obj.setKeySequence(key)
            except:
                pass

def grab_GC(window, settings: QtCore.QSettings):
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
