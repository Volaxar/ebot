from ibot.utils import *


# Создаем папку в закладках
def create_folder(folderName):
    if not get_folder_id(folderName):
        do_action(2 + rnd_keys(), 2 + rnd_keys() + len(folderName))
        
        sm.GetService('bookmarkSvc').CreateFolder(session.charid, folderName)


# Получаем ИД папки в закладках по имени
def get_folder_id(folder=None):
    for f in sm.GetService('bookmarkSvc').GetFoldersForOwner(session.charid):
        
        if f.folderName == folder:
            return f.folderID
    
    return None


# Получаем список закладок в папке
def get_bookmarks(folder=None, ignoreLocation=False):
    bookmarkSvc = sm.GetService('bookmarkSvc')
    all_bms = bookmarkSvc.GetMyBookmarks()
    
    folderID = get_folder_id(folder)
    
    bms = []
    
    for bm in all_bms.values():
        if bm.locationID == session.solarsystemid2 or ignoreLocation:
            if not folderID or folderID and bm.folderID == folderID:
                bms.append(bm)
    
    return bms


# Получить закладку по имени
def get_bookmark(label, folder=None, ignoreLocation=False):
    bookmarkSvc = sm.GetService('bookmarkSvc')
    bms = bookmarkSvc.GetMyBookmarks()
    
    folderID = get_folder_id(folder)
    
    for bm in bms.values():
        if bm.memo.strip() == label and (bm.locationID == session.solarsystemid2 or ignoreLocation):
            if not folderID or folderID and bm.folderID == folderID:
                return bm
    
    return None


# Создаем закладку
def set_bookmark(label, note='', folder=None):
    if get_bookmark(label):
        return
    
    if session.solarsystemid and session.shipid:
        bp = sm.GetService('michelle').GetBallpark(True)
        bmsvc = sm.GetService('bookmarkSvc')
        
        slimItem = bp.GetInvItem(session.shipid)
        
        folderID = get_folder_id(folder)
        
        do_action(2 + rnd_keys(), 2 + rnd_keys() + len(label))
        
        bmsvc.BookmarkLocation(session.shipid, session.charid, label, note, slimItem.typeID,
                               session.solarsystemid, folderID=folderID)


# Удаляем закладку
def del_bookmark(memo, folder=None):
    bm = get_bookmark(memo, folder)
    
    if bm:
        do_action(3 + rnd_keys())
        
        sm.GetService('bookmarkSvc').DeletePersonalBookmarks([bm.bookmarkID])
