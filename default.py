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
import os
import pickle

__settings__ = xbmcaddon.Addon(id='plugin.video.newznab')
__language__ = __settings__.getLocalizedString

USERDATA_PATH = xbmc.translatePath(__settings__.getAddonInfo("profile"))

NZBS_URL = "plugin://plugin.video.nzbs"

NS_REPORT = "http://www.newzbin.com/DTD/2007/feeds/report/"
NS_NEWZNAB = "http://www.newznab.com/DTD/2010/feeds/attributes/"

MODE_LIST = "list"
MODE_DOWNLOAD = "download"
MODE_INCOMPLETE = "incomplete"

MODE_INDEX = "index"
MODE_HIDE = "hide"
MODE_CART = "cart"
MODE_CART_DEL = "cart_del"
MODE_CART_ADD = "cart_add"
MODE_SEARCH = "search"
MODE_SEARCH_RAGEID = "search_rageid"
MODE_SEARCH_IMDB = "search_imdb"
MODE_FAVORITES = "favorites"
MODE_FAVORITES_TOP = "favorites_top"
MODE_FAVORITE_ADD = "favorites_add"
MODE_FAVORITE_DEL = "favorites_del"

MODE_NEWZNAB = "newznab"
MODE_NEWZNAB_SEARCH = "newznab&newznab=search"
MODE_NEWZNAB_SEARCH_RAGEID = "newznab&newznab=search_rageid"
MODE_NEWZNAB_SEARCH_IMDB = "newznab&newznab=search_imdb"
MODE_NEWZNAB_MY = "newznab&newznab=mycart"
        
def site_caps(index):
    url = "http://" + __settings__.getSetting("newznab_site_%s" % index) + "/api?t=caps"
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

def newznab(index, params = None):
    newznab_url = ("http://" + __settings__.getSetting("newznab_site_%s" % index) + "/rss?dl=1&i=" +\
                  __settings__.getSetting("newznab_id_%s" % index) + "&r=" +\
                  __settings__.getSetting("newznab_key_%s" % index))
    newznab_url_search = ("http://" + __settings__.getSetting("newznab_site_%s" % index) +\
                         "/api?dl=1&apikey=" + __settings__.getSetting("newznab_key_%s" % index))
    hide_cat = __settings__.getSetting("newznab_hide_cat_%s" % index)
    if params:
        get = params.get
        catid = get("catid")
        newznab_id = get("newznab")
        url = get("url")
        if url:
            url_out = urllib.unquote_plus(url)
        if newznab_id:
            if newznab_id == "mycart":
                url_out = newznab_url + "&t=-2"
            if newznab_id == "search":
                search_term = search(__settings__.getSetting("newznab_name_%s" % index), index)
                if search_term:
                    url_out = (newznab_url_search + "&t=search" + "&cat=" + catid + "&q=" 
                    + search_term + "&extended=1")
            if newznab_id == "search_rageid":
                rageid = get('rageid')
                url_out = (newznab_url_search + "&t=tvsearch" + "&rid=" + rageid + "&extended=1")
                if catid:
                    url_out = url_out + "&cat=" + catid
            if newznab_id == "search_imdb":
                imdb = get('imdb')
                url_out = (newznab_url_search + "&t=movie" + "&imdbid=" + imdb + "&extended=1")
        elif catid:
            url_out = newznab_url + "&t=" + catid
            key = "&catid=" + catid
            add_posts({'title' : 'Search...',}, index, url=key, mode=MODE_NEWZNAB_SEARCH)
        if url_out:
            list_feed_newznab(url_out, index)
    else:
        for name, catid in site_caps(index):
            if not re.search(hide_cat, catid, re.IGNORECASE) or not hide_cat:
                key = "&catid=" + str(catid)
                add_posts({'title' : name,}, index, url=key, mode=MODE_NEWZNAB)
        add_posts({'title' : "My Cart",}, index, mode=MODE_NEWZNAB_MY)
        add_posts({'title' : "Search Favorites",}, index, mode=MODE_FAVORITES_TOP)
        add_posts({'title' : 'Incomplete',}, 0, mode=MODE_INCOMPLETE)
        xbmcplugin.setContent(int(sys.argv[1]), 'movies')
        xbmcplugin.endOfDirectory(int(sys.argv[1]), succeeded=True, cacheToDisc=True)
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
        if 't=-2' in feedUrl:
            mode = MODE_CART
        elif 't=search' in feedUrl:
            mode = MODE_SEARCH
            params = get_parameters(feedUrl)
            get = params.get
            search_url = urllib.quote_plus(feedUrl)
            # search_term url encoded in search(..) method
            search_term = get('q')
        elif 't=tvsearch' in feedUrl:
            mode = MODE_SEARCH_RAGEID
            params = get_parameters(feedUrl)
            get = params.get
            search_url = urllib.quote_plus(feedUrl)
        elif 't=movie' in feedUrl:
            mode = MODE_SEARCH_IMDB
        else:
            mode = MODE_LIST
        for item in doc.getElementsByTagName("item"):
            info_labels = dict()
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
                info_labels['imdb'] = attribs['imdb']
                info_labels['code'] = 'tt' + attribs['imdb']
                # Append imdb id to the plot. Picked up by plugin.video.nzbs
                text = info_labels['plot'] + " code:" + info_labels['code']
                info_labels['plot'] = text
                #
            except:
                pass
            try:
                info_labels['rageid'] = attribs['rageid']
            except:
                pass
            try:
                info_labels['tvdb-show'] = attribs['tvdb-show']
            except:
                pass
            regex = re.compile("([1-9]?\d$)")
            try:
                info_labels['season'] = int(regex.findall(attribs['season'])[0])
            except:
                pass
            try:
                info_labels['episode'] = int(regex.findall(attribs['episode'])[0])
            except:
                pass
            try:
                info_labels['tvshowtitle'] = attribs['tvtitle']
            except:
                pass
            try:
                info_labels['aired'] = attribs['tvairdate']
            except:
                pass
            try:
                info_labels['category'] = attribs['category']
            except:
                pass
            nzb = get_node_value(item, "link")
            thumb_re = re.search(re_thumb, description, re.IGNORECASE|re.DOTALL)
            if thumb_re:
                regex = re.compile(re_thumb,re.IGNORECASE)
                thumb = regex.findall(description)[0]
            else:
                thumb = ""
            nzb = "&nzb=" + urllib.quote_plus(nzb) + "&nzbname=" + urllib.quote_plus(info_labels['title'])
            if mode == MODE_SEARCH:
                nzb = nzb + "&search_url=" + search_url + "&search_term=" + search_term
            if mode == MODE_SEARCH_RAGEID:
                nzb = nzb + "&search_url=" + search_url
            # Clear empty keys
            for key in info_labels.keys():
                if(info_labels[key] == -1):
                    del info_labels[key]
                try:
                    if (len(info_labels[key])<1):
                        del info_labels[key]
                except:
                    pass
            add_posts(info_labels, index, url=nzb, mode=mode, thumb=thumb)
        xbmcplugin.setContent(int(sys.argv[1]), 'movies')
        xbmcplugin.endOfDirectory(int(sys.argv[1]), succeeded=True, cacheToDisc=True)
    else:
        if state == "site":
            xbmc.executebuiltin('Notification("Newznab","Site down")')
        else:
            xbmc.executebuiltin('Notification("Newznab","Malformed result")')
    return

def add_posts(info_labels, index, **kwargs):
    url = ''
    if 'url' in kwargs:
        url = kwargs['url']
    mode = ''
    if 'mode' in kwargs:
        mode = kwargs['mode']
    thumb = ''
    if 'thumb' in kwargs:
        thumb = kwargs['thumb']
    folder = True
    if 'folder' in kwargs:
        folder = kwargs['folder']
    listitem=xbmcgui.ListItem(info_labels['title'], iconImage="DefaultVideo.png", thumbnailImage=thumb)
    fanart = thumb.replace('-cover','-backdrop')   
    listitem.setProperty("Fanart_Image", fanart)
    if mode == MODE_NEWZNAB:
        cm = []
        cm.append(cm_build("Hide", MODE_HIDE, url, index))
        listitem.addContextMenuItems(cm, replaceItems=True)
        xurl = "%s?mode=%s&index=%s" % (sys.argv[0], MODE_NEWZNAB, index)
    if mode == MODE_LIST or mode == MODE_CART or mode == MODE_SEARCH or\
       mode == MODE_SEARCH_RAGEID or mode == MODE_SEARCH_IMDB:
        mode_out = mode
        cm = []
        if (xbmcaddon.Addon(id='plugin.video.nzbs').getSetting("auto_play").lower() == "true"):
            folder = False
        cm_url_download = NZBS_URL + '?mode=' + MODE_DOWNLOAD + url
        cm.append(("Download", "XBMC.RunPlugin(%s)" % (cm_url_download)))
        if mode == MODE_CART:
            cm.append(cm_build("Remove from cart", MODE_CART_DEL, url, index))
            mode_out = MODE_LIST
        else:
            cm_mode = MODE_CART_ADD
            cm.append(cm_build("Add to cart", MODE_CART_ADD, url, index))
        if mode == MODE_SEARCH:
            cm.append(cm_build("Add to search favorites", MODE_FAVORITE_ADD, url, index))
            mode_out = MODE_LIST
        if mode == MODE_SEARCH_RAGEID:
            cm.append(cm_build("Add to search favorites", MODE_FAVORITE_ADD, url, index))
            mode_out = MODE_LIST
        if 'rageid' in info_labels:
            if mode != MODE_SEARCH_RAGEID: 
                url_search_rage = '&rageid=' + info_labels['rageid']
                cm.append(("Search for this show", "XBMC.Container.Update(%s?mode=%s%s&index=%s)" %\
                          (sys.argv[0], MODE_NEWZNAB_SEARCH_RAGEID, url_search_rage, index)))
            if mode == MODE_SEARCH_RAGEID:
                url_search_rage = '&rageid=' + info_labels['rageid'] + "&catid=" + info_labels['category']
                cm.append(("Search for this quality", "XBMC.Container.Update(%s?mode=%s%s&index=%s)" %\
                          (sys.argv[0], MODE_NEWZNAB_SEARCH_RAGEID, url_search_rage, index)))
        if 'imdb' in info_labels: 
            url_search_imdb = '&imdb=' + info_labels['imdb']
            cm.append(("Search for this movie", "XBMC.Container.Update(%s?mode=%s%s&index=%s)" %\
                     (sys.argv[0], MODE_NEWZNAB_SEARCH_IMDB, url_search_imdb, index)))
        if mode == MODE_SEARCH_IMDB:
            mode_out = MODE_LIST
        listitem.addContextMenuItems(cm, replaceItems=True)
        xurl = "%s?mode=%s" % (NZBS_URL,mode_out)
    elif mode == MODE_FAVORITES:
        cm = []
        cm.append(cm_build("Remove from search favorites", MODE_FAVORITE_DEL, url, index))
        listitem.addContextMenuItems(cm, replaceItems=True)
        xurl = "%s?mode=%s&index=%s" % (sys.argv[0], MODE_NEWZNAB, index)
    elif mode == MODE_INCOMPLETE:
        xurl = "%s?mode=%s" % (NZBS_URL,mode)
    else:
        xurl = "%s?mode=%s&index=%s" % (sys.argv[0], mode, index)
    xurl = xurl + url
    listitem.setInfo(type="Video", infoLabels=info_labels)
    listitem.setPath(xurl)
    return xbmcplugin.addDirectoryItem(handle=int(sys.argv[1]), url=xurl, listitem=listitem, isFolder=folder)

def cm_build(label, mode, url, index):
    command = "XBMC.RunPlugin(%s?mode=%s%s&index=%s)" % (sys.argv[0], mode, url, index)
    out = (label, command)
    return out

def hide_cat(index, params):
    get = params.get
    catid = get("catid")
    re_cat = '(\d)000'
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

def cart_del(index, params):
    get = params.get
    nzb = get("nzb")
    re_id = 'nzb%2F(d*b*.*)\.nzb'
    regex = re.compile(re_id,re.IGNORECASE)
    id = regex.findall(nzb)[0]
    url = "http://" + __settings__.getSetting("newznab_site_%s" % index) +\
          "/api?t=cartdel&apikey=" + __settings__.getSetting("newznab_key_%s" % index) +\
          "&id=" + id
    xbmc.executebuiltin('Notification("Newznab","Removing from cart")')
    load_xml(url)
    xbmc.executebuiltin("Container.Refresh")
    return

def cart_add(index, params):
    get = params.get
    nzb = get("nzb")
    re_id = 'nzb%2F(d*b*.*)\.nzb'
    regex = re.compile(re_id,re.IGNORECASE)
    id = regex.findall(nzb)[0]
    url = "http://" + __settings__.getSetting("newznab_site_%s" % index) +\
          "/api?t=cartadd&apikey=" + __settings__.getSetting("newznab_key_%s" % index) +\
          "&id=" + id
    xbmc.executebuiltin('Notification("Newznab","Adding to cart")')
    load_xml(url)
    return

# FROM plugin.video.youtube.beta  -- converts the request url passed on by xbmc to our plugin into a dict  
def get_parameters(parameterString):
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
    # TODO
    # Cache the url calls
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

def favorites(index):
    # http://wiki.python.org/moin/UsingPickle
    favorite_filename = "favorite_" + index + ".p"
    favorite = os.path.join(USERDATA_PATH, favorite_filename)
    try:
        favorite_dict = pickle.load( open( favorite, "rb" ) )
    except:
        return
    for key, value in favorite_dict.iteritems():
        info_labels = dict()
        info_labels['title'] = key
        url = "&url=" + value
        add_posts(info_labels, index, url=url, mode=MODE_FAVORITES)
    xbmcplugin.setContent(int(sys.argv[1]), 'movies')
    xbmcplugin.endOfDirectory(int(sys.argv[1]), succeeded=True, cacheToDisc=True)


def favorite_add(index, params):
    get = params.get
    search_term = get('search_term')
    search_url = get('search_url')
    nzbname = get('nzbname')
    if search_term is None and nzbname is not None:
        search_term = nzbname
    else:
        search_term = ''
    key = ''
    while len(key) < 1:
        key = unikeyboard(search_term, 'Favorite name')
    favorite_filename = "favorite_" + index + ".p"
    favorite = os.path.join(USERDATA_PATH, favorite_filename)
    try:
        favorite_dict = pickle.load( open( favorite, "rb" ) )
    except:
        favorite_dict = dict()
    favorite_dict[key] = search_url
    pickle.dump( favorite_dict, open( favorite, "wb" ) )
    return

def favorite_del(index):
    key = xbmc.getInfoLabel( "ListItem.Title" )
    favorite_filename = "favorite_" + index + ".p"
    favorite = os.path.join(USERDATA_PATH, favorite_filename)
    favorite_dict = pickle.load( open( favorite, "rb" ) )
    del favorite_dict[key]
    pickle.dump( favorite_dict, open( favorite, "wb" ) )
    xbmc.executebuiltin("Container.Refresh")
    return

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
        add_posts({'title': __settings__.getSetting("newznab_name_%s" % index)}, index, mode=MODE_INDEX)
    xbmcplugin.setContent(int(sys.argv[1]), 'movies')
    xbmcplugin.endOfDirectory(int(sys.argv[1]), succeeded=True, cacheToDisc=True)
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
            newznab('1')
        elif len(index_list) >= 1:
            show_site_list(index_list)
        else:
            __settings__.openSettings()
    else:
        params = get_parameters(sys.argv[2])
        get = params.get
        if get("mode")== MODE_INDEX:
            newznab(get("index"))
        if get("mode")== MODE_NEWZNAB:
            newznab(get("index"), params)
        if get("mode")== MODE_HIDE:
            hide_cat(get("index"), params)
        if get("mode")== MODE_CART_DEL:
            cart_del(get("index"), params)
        if get("mode")== MODE_CART_ADD:
            cart_add(get("index"), params)
        if get("mode")== MODE_FAVORITES_TOP:
            favorites(get("index"))
        if get("mode")== MODE_FAVORITE_ADD:
            favorite_add(get("index"), params)
        if get("mode")== MODE_FAVORITE_DEL:
            favorite_del(get("index"))
