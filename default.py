"""
 Copyright (c) 2010, 2011, 2012 Popeye

 Permission is hereby granted, free of charge, to any person
 obtaining a copy of this software and associated documentation
 files (the "Software"), to deal in the Software without
 restriction, including without limitation the rights to use,
 copy, modify, merge, publish, distribute, sublicense, and/or sell
 copies of the Software, and to permit persons to whom the
 Software is furnished to do so, subject to the following
 conditions:

 The above copyright notice and this permission notice shall be
 included in all copies or substantial portions of the Software.

 THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
 EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES
 OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
 NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
 HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
 WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
 FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
 OTHER DEALINGS IN THE SOFTWARE.
"""

import urllib
import urllib2
import re
import xbmcaddon
import xbmcgui
import xbmcplugin
from xml.dom.minidom import parse, parseString

__settings__ = xbmcaddon.Addon(id='plugin.video.newznab')
__language__ = __settings__.getLocalizedString

NZBS_URL = "plugin://plugin.video.nzbs"

NS_REPORT = "http://www.newzbin.com/DTD/2007/feeds/report/"
NS_NEWZNAB = "http://www.newznab.com/DTD/2010/feeds/attributes/"

MODE_LIST = "list"
MODE_DOWNLOAD = "download"
MODE_INCOMPLETE = "incomplete"
MODE_INDEX = "index"
MODE_HIDE = "hide"

MODE_NEWZNAB = "newznab"
MODE_NEWZNAB_SEARCH = "newznab&newznab=search"
MODE_NEWZNAB_MY = "newznab&newznab=mycart"
        
def site_caps(url):
    doc, state = load_xml(url)
    if doc and not state:
        table = []
        for category in doc.getElementsByTagName("category"):
            row = []
            row.append(category.getAttribute("name"))
            row.append(category.getAttribute("id"))
            table.append(row)
            if category.getElementsByTagName("subcat"):
                for subcat in category.getElementsByTagName("subcat"):
                    row = []
                    row.append((" - " + subcat.getAttribute("name")))
                    row.append(subcat.getAttribute("id"))
                    table.append(row)
    return table

def newznab(params, index):
    newznab_url = ("http://" + __settings__.getSetting("newznab_site_%s" % index) + "/rss?dl=1&i=" +\
                  __settings__.getSetting("newznab_id_%s" % index) + "&r=" +\
                  __settings__.getSetting("newznab_key_%s" % index))
    newznab_url_search = ("http://" + __settings__.getSetting("newznab_site_%s" % index) +\
                         "/api?dl=1&apikey=" + __settings__.getSetting("newznab_key_%s" % index))
    hide_cat = __settings__.getSetting("newznab_hide_cat_%s" % index)
    site_caps_url = "http://" + __settings__.getSetting("newznab_site_%s" % index) + "/api?t=caps"
    if params:
        get = params.get
        catid = get("catid")
        newznab = get("newznab")
        url = None
        if newznab:
            if newznab == "mycart":
                url = newznab_url + "&t=-2"
            if newznab == "search":
                search_term = search(__settings__.getSetting("newznab_name_%s" % index), index)
                if search_term:
                    url = (newznab_url_search + "&t=search" + "&cat=" + catid + "&q=" 
                    + search_term)
        elif catid:
            url = newznab_url + "&t=" + catid
            key = "&catid=" + catid + "&index=" + index
            add_posts({'title' : 'Search...',}, key, MODE_NEWZNAB_SEARCH)
        if url:
            list_feed_newznab(url, index)
    else:
        for name, catid in site_caps(site_caps_url):
            if not re.search(hide_cat, catid, re.IGNORECASE) or not hide_cat:
                key = "&catid=" + str(catid) + "&index=" + index
                add_posts({'title' : name,}, key, MODE_NEWZNAB)
        add_posts({'title' : "My Cart",}, ("&index=" + index), MODE_NEWZNAB_MY)
        add_posts({'title' : 'Incomplete',}, '', MODE_INCOMPLETE)
    xbmcplugin.setContent(int(sys.argv[1]), 'movies')
    return

def list_feed_newznab(feedUrl, index):
    re_rating = __settings__.getSetting("newznab_re_rating_%s" % index)
    re_plot = __settings__.getSetting("newznab_re_plot_%s" % index)
    re_year = __settings__.getSetting("newznab_re_year_%s" % index)
    re_genre = __settings__.getSetting("newznab_re_genre_%s" % index)
    re_director = __settings__.getSetting("newznab_re_director_%s" % index)
    re_actors = __settings__.getSetting("newznab_re_actors_%s" % index)
    re_thumb = __settings__.getSetting("newznab_re_thumb_%s" % index).replace("SITE_URL", __settings__.getSetting("newznab_site_%s" % index))
    doc, state = load_xml(feedUrl)
    if doc and not state:
        info_labels = dict()
        for item in doc.getElementsByTagName("item"):
            info_labels['title'] = get_node_value(item, "title")
            description = get_node_value(item, "description")
            rating = re.search(re_rating, description, re.IGNORECASE|re.DOTALL)
            if rating:
                info_labels['rating'] = float(rating.group(1))
            plot = re.search(re_plot, description, re.IGNORECASE|re.DOTALL)
            if plot:
                info_labels['plot'] = plot.group(1)
            year = re.search(re_year, description, re.IGNORECASE|re.DOTALL)
            if year:
                info_labels['year'] = int(year.group(1))
            genre = re.search(re_genre, description, re.IGNORECASE|re.DOTALL)
            if genre:
                info_labels['genre'] = genre.group(1)
            director = re.search(re_director, description, re.IGNORECASE|re.DOTALL)
            if director:
                info_labels['director'] = director.group(1)
            actors = re.search(re_actors, description, re.IGNORECASE|re.DOTALL)
            if actors:
                info_labels['cast'] = actors.group(1).split(',')
            attribs = dict()
            for attr in item.getElementsByTagName("newznab:attr"):
                attribs[attr.getAttribute("name")] = attr.getAttribute("value")
            try:
                info_labels['size'] = int(attribs['size'])
            except:
                pass
            try:
                info_labels['code'] = 'tt' + attribs['imdb']
                # Append imdb id to the plot. Picked up by plugin.video.nzbs
                text = info_labels['plot'] + " code:" + info_labels['code']
                info_labels['plot'] = text
                #
            except:
                pass
            nzb = get_node_value(item, "link")
            thumb_re = re.search(re_thumb, description, re.IGNORECASE|re.DOTALL)
            if thumb_re:
                regex = re.compile(re_thumb,re.IGNORECASE)
                thumb = regex.findall(description)[0]
            else:
                thumb = ""
            nzb = "&nzb=" + urllib.quote_plus(nzb) + "&nzbname=" + urllib.quote_plus(info_labels['title'].encode('utf-8')) +\
                  "&index=" + index
            mode = MODE_LIST
            add_posts(info_labels, nzb, mode, thumb)
        xbmcplugin.setContent(int(sys.argv[1]), 'movies')
    else:
        if state == "site":
            xbmc.executebuiltin('Notification("Newznab","Site down")')
        else:
            xbmc.executebuiltin('Notification("Newznab","Malformed result")')
    return

def add_posts(info_labels, url, mode, thumb = '', folder=True):
    listitem=xbmcgui.ListItem(info_labels['title'], iconImage="DefaultVideo.png", thumbnailImage=thumb)
    listitem.setInfo(type="Video", infoLabels=info_labels)
    fanart = thumb.replace('-cover','-backdrop')
    listitem.setProperty("Fanart_Image", fanart)
    if mode == MODE_NEWZNAB:
        cm = []
        cm_mode = MODE_HIDE
        cm_label = "Hide"
        cm_url_hide = sys.argv[0] + '?mode=' + cm_mode + url
        cm.append((cm_label , "XBMC.RunPlugin(%s)" % (cm_url_hide)))
        listitem.addContextMenuItems(cm, replaceItems=False)
        xurl = "%s?mode=%s" % (sys.argv[0],mode)
    if mode == MODE_LIST:
        cm = []
        cm_mode = MODE_DOWNLOAD
        cm_label = "Download"
        if (xbmcaddon.Addon(id='plugin.video.nzbs').getSetting("auto_play").lower() == "true"):
            folder = False
        cm_url_download = NZBS_URL + '?mode=' + cm_mode + url
        cm.append((cm_label , "XBMC.RunPlugin(%s)" % (cm_url_download)))
        listitem.addContextMenuItems(cm, replaceItems=False)
        xurl = "%s?mode=%s" % (NZBS_URL,mode)
    elif mode == MODE_INCOMPLETE:
        xurl = "%s?mode=%s" % (NZBS_URL,mode)
    else:
        xurl = "%s?mode=%s" % (sys.argv[0],mode)
    xurl = xurl + url
    listitem.setPath(xurl)
    return xbmcplugin.addDirectoryItem(handle=int(sys.argv[1]), url=xurl, listitem=listitem, isFolder=folder)

def hide_cat(params):
    get = params.get
    catid = get("catid")
    re_cat = '(\d)000'
    index = get("index")
    hide_cat = __settings__.getSetting("newznab_hide_cat_%s" % index)
    if re.search(re_cat, catid, re.IGNORECASE):
        regex = re.compile(re_cat,re.IGNORECASE)
        new_cat = regex.findall(catid)[0] + "\d\d\d"
        if hide_cat:
            new_cat = new_cat + "|" +  hide_cat
    else:
        new_cat = catid
        if hide_cat:
            new_cat = new_cat + "|" +  hide_cat
    __settings__.setSetting("newznab_hide_cat_%s" % index, new_cat)
    xbmc.executebuiltin("Container.Refresh")
    return

# FROM plugin.video.youtube.beta  -- converts the request url passed on by xbmc to our plugin into a dict  
def getParameters(parameterString):
    commands = {}
    splitCommands = parameterString[parameterString.find('?')+1:].split('&')
    for command in splitCommands: 
        if (len(command) > 0):
            splitCommand = command.split('=')
            name = splitCommand[0]
            value = splitCommand[1]
            commands[name] = value
    
    return commands

def get_node_value(parent, name, ns=""):
    if ns:
        return parent.getElementsByTagNameNS(ns, name)[0].childNodes[0].data.encode('utf-8')
    else:
        return parent.getElementsByTagName(name)[0].childNodes[0].data.encode('utf-8')

def load_xml(url):
    try:
        req = urllib2.Request(url)
        response = urllib2.urlopen(req)
    except:
        xbmc.log("plugin.video.newznab: unable to load url: " + url)
        return None, "site"
    xml = response.read()
    response.close()
    try:
        out = parseString(xml)
    except:
        xbmc.log("plugin.video.newznab: malformed xml from url: " + url)
        return None, "xml"
    return out, None

def search(dialog_name, index):
    searchString = unikeyboard(__settings__.getSetting( "latestSearch" ), ('Search ' +\
                   __settings__.getSetting("newznab_name_%s" % index)) )
    if searchString == "":
        xbmcgui.Dialog().ok('Newznab','Missing text')
    elif searchString:
        latestSearch = __settings__.setSetting( "latestSearch", searchString )
        dialogProgress = xbmcgui.DialogProgress()
        dialogProgress.create(dialog_name, 'Searching for: ' , searchString)
        #The XBMC onscreen keyboard outputs utf-8 and this need to be encoded to unicode
    encodedSearchString = urllib.quote_plus(searchString.decode("utf_8").encode("raw_unicode_escape"))
    return encodedSearchString

#From old undertexter.se plugin    
def unikeyboard(default, message):
    keyboard = xbmc.Keyboard(default, message)
    keyboard.doModal()
    if (keyboard.isConfirmed()):
        return keyboard.getText()
    else:
        return ""

def import_settings():
    try:
        nzbsu_settings = xbmcaddon.Addon(id='plugin.video.nzbsu')
        key = nzbsu_settings.getSetting("nzb_su_key")
        id = nzbsu_settings.getSetting("nzb_su_id")
        __settings__.setSetting("newznab_id_1", id)
        __settings__.setSetting("newznab_key_1", key)
        __settings__.setSetting("newznab_site_1", 'nzb.su')
        __settings__.setSetting("newznab_name_1", 'Nzb.su')
    except:
        pass
    return

def get_index_list():
    index_list = []
    for i in range(1, 6):
        if __settings__.getSetting("newznab_id_%s" % i):
            index_list.append(i)
    return index_list

def show_site_list(index_list):
    for index in index_list:
        add_posts({'title': __settings__.getSetting("newznab_name_%s" % index)}, ('&index=%s' % index), MODE_INDEX)
    xbmcplugin.setContent(int(sys.argv[1]), 'movies')
    return

if (__name__ == "__main__" ):
    if not (__settings__.getSetting("firstrun") and __settings__.getSetting("newznab_id_1")
        and __settings__.getSetting("newznab_key_1")):
        import_settings()
        __settings__.openSettings()
        __settings__.setSetting("firstrun", '1')
    if (not sys.argv[2]):
        index_list = get_index_list()
        if len(index_list) == 1:
            newznab(None, '1')
        elif len(index_list) >= 1:
            show_site_list(index_list)
        else:
            __settings__.openSettings()
    else:
        params = getParameters(sys.argv[2])
        get = params.get
        if get("mode")== MODE_INDEX:
            newznab(None, get("index"))
        if get("mode")== MODE_NEWZNAB:
            newznab(params, get("index"))
        if get("mode")== MODE_HIDE:
            hide_cat(params)

xbmcplugin.endOfDirectory(int(sys.argv[1]), succeeded=True, cacheToDisc=True)