import form
import util

from ibot.utils import *


# Получить экземпляр блокнота
def get_notepad(hide=True):
    if not form.Notepad.IsOpen():
        do_action(3 + rnd_keys())
        
        form.Notepad.Open()
    
    notepad = form.Notepad.GetIfOpen()
    
    if notepad.IsVisible() and hide:
        do_action(1 + rnd_keys())
        
        notepad.Hide()
    
    while not notepad.GetNotes(0):
        pause(100)
    
    return notepad


# Получить ид папки блокнота по имени
def get_note_folder_id(name=None):
    notepad = get_notepad()
    
    for folder in notepad.GetFolders():
        if folder.label == name:
            return folder.noteID
    
    return 0


# Список записей в папке
def get_notes(folder=None):
    notepad = get_notepad()
    
    lst = notepad.GetNotes(get_note_folder_id(folder))
    
    notes = []
    
    for value in lst.values():
        if 'N:' + str(value.data) in notepad.notes:
            notes.append(notepad.GetNoteText(int(value.data)))
    
    return notes


# Получить запись по имени
def get_note_by_name(name, folder=None):
    notes = get_notes(folder)
    
    for note in notes:
        if note.label == name:
            return note
    
    return None


# Добавить запись
def add_note(name, text, folder=None):
    notepad = get_notepad()
    
    if notepad.AlreadyExists('N', name):
        note = get_note_by_name(name, folder)
        
        if note:
            new_text = text.split('<br>')
            old_text = note.text.split('<br>')
            
            add = []
            
            for t in new_text:
                if ':' in t:
                    continue
                
                if t not in old_text:
                    add.append(t)
            
            del old_text[0]
            
            all_text = '<br>'.join([new_text[0]] + old_text + add)
            
            upd_note(name, all_text, folder)
        
        return None
    
    noteID = sm.RemoteSvc('charMgr').AddOwnerNote('N:' + name, '<br>')
    
    folderID = get_note_folder_id(folder)
    
    if folderID:
        notepad.AddNote(folderID, 'N', noteID)
    
    n = util.KeyVal()
    n.noteID = noteID
    n.label = name
    n.text = '<br>'
    notepad.notes['N:' + str(noteID)] = n
    
    notepad.LoadNotes()
    
    do_action(5 + rnd_keys(), 2 + rnd_keys() + len(name) + len(text))
    
    upd_note(name, text, folder)
    
    return noteID


# Изменить текст записи
def upd_note(name, text, folder=None):
    notepad = get_notepad()
    
    if notepad.AlreadyExists('N', name):
        note = get_note_by_name(name, folder)
        
        if note.text != text:
            notepad.ShowNote('N:' + str(note.noteID))
            
            notepad.sr.browser.SetValue(text)
            
            do_action(3 + rnd_keys(), rnd_keys() + len(text))
            
            notepad.SaveNote()


# Удалить запись
def del_note(name, folder=None):
    notepad = get_notepad()
    
    note = get_note_by_name(name, folder)
    
    if note:
        noteID = 'N:' + str(note.noteID)
        
        if notepad.activeNode == noteID:
            notepad.activeNode = None
            notepad.ShowNote(None)
        
        t, _id = noteID.split(':')
        for key, value in notepad.folders.items():
            if value.type == t and int(value.data) == _id:
                del notepad.folders[key]
        
        do_action(5 + rnd_keys())
        
        sm.RemoteSvc('charMgr').RemoveOwnerNote(int(note.noteID))
        del notepad.notes[noteID]
        notepad.LoadNotes()
