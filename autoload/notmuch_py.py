#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# vim:fileencoding=utf-8 fileformat=unix
#
# Author:  Iranoan <iranoan+vim@gmail.com>
# License: GPL Ver.3.

try:
    import vim
    VIM_MODULE = True            # vim から読み込まれたか?
except ModuleNotFoundError:
    VIM_MODULE = False
import notmuch
import mailbox
import email
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from html2text import HTML2Text     # HTML メールの整形
from subprocess import Popen, PIPE, run, TimeoutExpired  # API で出来ないことは notmuch コマンド
import os                           # ディレクトリの存在確認、作成
import time                         # UNIX time の取得
import shutil                       # ファイル移動
import sys                          # プロセス終了
import datetime                     # 日付
import re                           # 正規表現
import glob                         # ワイルドカード展開
from operator import attrgetter     # ソート
# from operator import itemgetter, attrgetter  # ソート
from hashlib import sha256          # ハッシュ
import mimetypes                    # ファイルの MIMETYPE を調べる
import locale
from urllib.parse import unquote    # URL の %xx を変換
# import copy
import concurrent.futures


def print_warring(msg):
    if VIM_MODULE:
        vim.command('redraw | echohl WarningMsg | echomsg "' + msg + '" | echohl None')
    else:
        sys.stderr.write(msg)


def print_err(msg):  # エラー表示だけでなく終了
    if VIM_MODULE:
        vim.command('echohl ErrorMsg | echomsg "' + msg + '" | echohl None')
    else:
        sys.stderr.write(msg)
        sys.exit()
    delete_gloval_variable()


def print_error(msg):  # エラーとして表示させるだけ
    if VIM_MODULE:
        vim.command('echohl ErrorMsg | echomsg "' + msg + '" | echohl None')
    else:
        sys.stderr.write(msg)


# グローバル変数の初期値 (vim からの設定も終わったら変化させない定数扱い)
# Subject の先頭から削除する正規表現文字列
if not ('DELETE_TOP_SUBJECT' in globals()):
    DELETE_TOP_SUBJECT = r'^\s*((R[Ee][: ]*\d*)?\[[A-Za-z -]+(:\d+)?\](\s*R[Ee][: ])?\s*' + \
        r'|(R[Ee][: ]*\d*)?\w+\.\d+:\d+\|( R[Ee][: ]\d+)? ?' + \
        r'|R[Ee][: ]+)*[　 ]*'
try:  # Subject の先頭文字列
    RE_SUBJECT = re.compile(DELETE_TOP_SUBJECT)
except re.error:
    print_warring('Error: Regurlar Expression.' +
                  '\nReset g:notmuch_delete_top_subject: ' + DELETE_TOP_SUBJECT +
                  '\nusing default settings.')
    DELETE_TOP_SUBJECT = r'^\s*((R[Ee][: ]*\d*)?\[[A-Za-z -]+(:\d+)?\](\s*R[Ee][: ])?\s*' + \
        r'|(R[Ee][: ]*\d*)?\w+\.\d+:\d+\|( R[Ee][: ]\d+)? ?' + \
        r'|R[Ee][: ]+)*[　 ]*'
    try:  # 先頭空白削除
        RE_SUBJECT = re.compile(DELETE_TOP_SUBJECT)
    except re.error:
        print_err('Error: Regurlar Expression')
# スレッドに表示する Date の書式
if not ('DATE_FORMAT' in globals()):
    DATE_FORMAT = '%Y-%m-%d %H:%M'
# フォルダー・リストのフォーマット
if not ('FOLDER_FORMAT' in globals()):
    FOLDER_FORMAT = '{0:<14} {1:>3}/{2:>5}|{3:>3} [{4}]'
# スレッドの各行に表示する順序
if not ('DISPLAY_ITEM' in globals()):
    DISPLAY_ITEM = ('Subject', 'From', 'Date')
DISPLAY_ITEM = (DISPLAY_ITEM[0].lower(), DISPLAY_ITEM[1].lower(), DISPLAY_ITEM[2].lower())
# ↑vim の設定が有っても小文字には変換する
# スレッドの各行に表示する From の長さ
if not ('FROM_LENGTH' in globals()):
    FROM_LENGTH = 21
# スレッドの各行に表示する Subject の長さ
if not ('SUBJECT_LENGTH' in globals()):
    SUBJECT_LENGTH = 80 - FROM_LENGTH - 16 - 4
# 送信済みを表すタグ
if not ('SENT_TAG' in globals()):
    SENT_TAG = 'sent'
# 送信プログラムやそのパラメータ
if not ('SEND_PARAM' in globals()):
    SEND_PARAM = ['sendmail', '-t', '-oi']
# 送信文字コード
if not ('SENT_CHARCODE' in globals()):
    SENT_CHARSET = ['us-ascii', 'iso-2022-jp', 'utf-8']
# Mailbox の種類
if not ('MAILBOX_TYPE' in globals()):
    MAILBOX_TYPE = 'Maildir'
# 添付ファイルの一時展開先等 plugin/autoload ディレクトリに *.vim/*.py があるのでその親ディレクトリに作成
if not VIM_MODULE:
    TEMP_DIR = os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))).replace('/', os.sep)+os.sep
    # CACHE_DIR = TEMP_DIR+'.cache'+os.sep
    ATTACH_DIR = TEMP_DIR+'attach'+os.sep
    TEMP_DIR += '.temp'+os.sep
# else:  # __file__は vim から無理↓もだめなので、vim スクリプト側で設定
#     CACHE_DIR = vim.eval('expand("<sfile>:p:h:h")')+os.sep+'.cache'+os.sep
# スレッド・リスト・データのリスト
THREAD_LISTS = {}
# 他には DBASE, PATH, GLOBALS


def get_subject_length():  # スレッド・リストに表示する Subject の幅を計算
    global SUBJECT_LENGTH, FROM_LENGTH
    if 'notmuch_subject_length' in vim.vars:
        SUBJECT_LENGTH = vim.vars['notmuch_subject_length']
        return
    width = vim.vars['notmuch_open_way']['thread'].decode()
    m = re.search(r'([0-9]+)vnew', width)
    if m is not None:
        width = int(m.group(1)) - 1
    else:
        m = re.search('vnew', width)
        if m is None:
            width = vim.options['columns']
        else:
            width = vim.options['columns'] / 2 - 1
    foldcolumn = vim.current.window.options['foldcolumn']
    if not foldcolumn:
        foldcolumn = 2
    width -= len(datetime.datetime.now().strftime(DATE_FORMAT)) + \
        2 + 2 + foldcolumn + 2
    # 最後の数字は、区切りのタブ*2, sing, fold, ウィンドウ境界
    if SUBJECT_LENGTH < FROM_LENGTH * 2:
        SUBJECT_LENGTH = int(width * 2 / 3)
        FROM_LENGTH = width - SUBJECT_LENGTH
    else:
        SUBJECT_LENGTH = width - FROM_LENGTH


def delete_gloval_variable():
    global ATTACH_DIR, DATE_FORMAT, DELETE_TOP_SUBJECT, \
        DISPLAY_ITEM, FOLDER_FORMAT, FROM_LENGTH, SENT_TAG, SUBJECT_LENGTH,\
        THREAD_LISTS, SEND_PARAM, SENT_CHARSET
    del ATTACH_DIR, DATE_FORMAT, DELETE_TOP_SUBJECT,\
        DISPLAY_ITEM, FOLDER_FORMAT, FROM_LENGTH, SENT_TAG, SUBJECT_LENGTH, \
        THREAD_LISTS, SEND_PARAM, SENT_CHARSET


# 変数によっては正規表現チェック+正規表現検索方法をパックしておく←主にスレッド・リストで使用
try:  # 先頭空白削除
    RE_TOP_SPACE = re.compile(r'^\s+')
except re.error:
    print_err('Error: Regurlar Expression')
try:  # 行末空白削除
    RE_END_SPACE = re.compile(r'\s*$')
except re.error:
    print_err('Error: Regurlar Expression')
try:  # タブと全角空白→スペース←スレッド・リストではできるだけ短く、タブはデリミタに使用予定
    RE_TAB2SPACE = re.compile('[　\t]+')
except re.error:
    print_err('Error: Regurlar Expression')
try:  # "に挟まれていれば挟まれている部分だけに
    RE_DQUOTE = re.compile(r'\s*"([^"]+)"\s*')
except re.error:
    print_err('Error: Regurlar Expression')


def email2only_name(mail_address):  # ヘッダの「名前+アドレス」を名前だけにする
    name, addr = email.utils.parseaddr(mail_address)
    if name == '':
        return mail_address
    return name


def email2only_address(mail_address):  # ヘッダの「名前+アドレス」をアドレスだけにする
    name, addr = email.utils.parseaddr(mail_address)
    return addr


def str_just_length(string, length):
    # 全角/半角どちらも桁数ではなくで幅に揃える (足りなければ空白を埋める)
    # →http://nemupm.hatenablog.com/entry/2015/11/25/202936 参考
    if VIM_MODULE:
        count_widht = vim.bindeval('strdisplaywidth(\'' + string.replace('\'', '\'\'') + '\')')
        if count_widht == length:
            return string
        elif count_widht < length:
            return string + ' ' * (length - count_widht)
        ambiwidth = (vim.options['ambiwidth'] == b'double')
    else:
        ambiwidth = 1
    if ambiwidth:
        symbol = '⌚⌛⏩⏪⏫⏬⏰⏳' + \
            '±µ¶×ø■□▲△▶▷▼▽◀◁◆◇◈○◎●◢◣◤◥◯◽◾' + \
            '★☆☉☎☏☔☕☜☞♀♂♈♉♊♋♌♍♎♏♐♑♒♓♠♡♣♤♥♧♨♩♪♬♭♯⚓⚞⚟⚡' + \
            '⚪⚫⚽⚾⚿⛄⛅⛇⛈⛉⛊⛋⛌⛎⛏⛐⛑⛒⛓⛔⛕⛖⛗⛘⛙⛚⛛⛜⛝⛞⛟⛠⛡' + \
            '⛨⛩⛪⛫⛬⛭⛮⛯⛰⛱⛲⛳⛴⛵⛶⛷⛸⛹⛺⛻⛼⛽⛾⛿' + \
            '∀∀∂∃∇∈∋∏∑∕√∝∞∟∠∣∥∧∨∩∩∪∫∬∮∵∵∶∼∽≈≒≠≡≤≥≦≧≪≫≮≯⊃⊆⊇⊕⊙⊥⊿'
    else:
        symbol = '⌚⌛⏩⏪⏫⏬⏰⏳' + \
            '◽◾' + \
            '☕♉♊♋♌♍♎♏♐♑♒♓⚓⚡' + \
            '⚪⚫⚽⚾⛄⛅⛎⛔' + \
            '⛪⛲⛳⛵⛺⛽'
    count_widht = 0
    count_char = 0
    ambiwidth += 1  # ambiwidth が double かどうかのフラグから、その文字幅の数値に変換
    for char in string:  # .decode('utf-8'):  # プロンプトから実行した時にエラーに成る
        char_code = ord(char)
        if char_code >= 0x391 and char_code <= 0x337:        # ギリシャ大文字
            count_widht += ambiwidth
        elif char_code >= 0x3B1 and char_code <= 0x3C9:      # ギリシャ小文字
            count_widht += ambiwidth
        elif char_code >= 0x2000 and char_code <= 0x206F:    # 一般句読点
            count_widht += 2
        elif (char_code >= 0x215B and char_code <= 0x215E) \
                or (char_code >= 0x2160 and char_code <= 0x216B) \
                or (char_code >= 0x2170 and char_code <= 0x2179):  # ローマ数字など数字に準じるもの
            count_widht += ambiwidth
        elif (char_code >= 0x2190 and char_code <= 0x2199) \
                or char_code == 0x21B8 or char_code == 0x21B9 \
                or char_code == 0x21D2 or char_code == 0x21E7:  # ←↑→↓↔↕↖↗↘↙ ↸↹ ⇒ ⇧
            count_widht += ambiwidth
        elif char_code >= 0x2460 and char_code <= 0x253C:    # 囲み数字と全角罫線
            count_widht += 2
        elif char in symbol:                                 # コードが固まっていない記号
            count_widht += 2
        elif char_code >= 0x3000 and char_code <= 0x30FF:    # CJK 記号句読点、かな文字
            count_widht += 2
        elif char_code >= 0x31F0 and char_code <= 0x9FEF:    # かな文字拡張 CJK 囲み文字/漢字など
            count_widht += 2
        elif char_code >= 0xAC00 and char_code <= 0xD7FB:    # ハングル
            count_widht += 2
        elif char_code >= 0xF900 and char_code <= 0xFAD9:    # CJK 互換
            count_widht += 2
        elif char_code >= 0xFE10 and char_code <= 0xFE19:    # 縦書形
            count_widht += 2
        elif char_code >= 0xFE30 and char_code <= 0xFE6B:    # CJK 互換形
            count_widht += 2
        elif char_code >= 0xFF00 and char_code <= 0xFF64:    # ASCII の全角形(･を除く)
            count_widht += 2
        # ASCII の全角形(･を除く)の続き
        elif char_code >= 0xFF66 and char_code <= 0xFFEE:
            count_widht += 2
        elif char_code >= 0x1F300 and char_code <= 0x1F64F:  # 顔文字・絵文字
            count_widht += 2
        elif char_code >= 0x20000 and char_code <= 0x2FA1D:  # CJK 結合拡張
            count_widht += 2
            # ↑他にもあると思うけど見つかったら追加していく
        else:
            count_widht += 1
        count_char += 1
        if count_widht == length:
            return string[0:count_char]
        elif count_widht > length:
            return string[0:count_char-1]+' '
    return string+(length-count_widht) * ' '


class MailData:  # メール毎の各種データ
    def __init__(self, msg, thread, order, depth):
        # self.__date = msg.get_date()                   # 日付 (time_t)
        self._newest_date = thread.get_newest_date()  # 同一スレッド中で最も新しい日付 (time_t)
        self.__thrd_order = order                     # 同一スレッド中の表示順
        self.__thrd_depth = depth                     # 同一スレッド中での深さ
        self._msg_id = msg.get_message_id()           # Message-ID
        self.__subject = msg.get_header('Subject')
        # self.__path = msg.get_filenames().__str__().split('\n')  # file name (full path)
        # ↑同一 Message-ID メールが複数でも取り敢えず全て
        # 整形した日付
        self.__reformed_date = RE_TAB2SPACE.sub(
            ' ', datetime.datetime.fromtimestamp(msg.get_date()).strftime(DATE_FORMAT))
        # 整形した Subject
        self.__reformed_subject = RE_TAB2SPACE.sub(
            ' ', RE_END_SPACE.sub('', RE_SUBJECT.sub('', self.__subject)))
        # 整形した宛名
        m_from = msg.get_header('From')
        try:
            m_to = msg.get_header('To')
        except notmuch.errors.NullPointerError:  # どの様な条件で起きるのか不明なので、取り敢えず From ヘッダを使う
            print('Message-ID:' + self._msg_id +
                  'notmuch.errors.NullPointerError')
            m_to = m_from
        # ↓From, To が同一なら From←名前が入っている可能性がより高い
        if email2only_address(m_to) == email2only_address(m_from):
            name = RE_TAB2SPACE.sub(' ', email2only_name(m_from))
        else:  # それ以外は送信メールなら To だけにしたいので、リスト利用
            tagslist = msg.get_tags().__str__().split()
            # 実際の判定 (To と Reply-To が同じなら ML だろうから除外)
            if SENT_TAG in tagslist \
                    and email2only_address(m_to) != email2only_address(msg.get_header('Reply-To')) \
                    and m_to != '':
                name = 'To:'+email2only_name(m_to)
            else:
                name = RE_TAB2SPACE.sub(' ', email2only_name(m_from))
        self.__reformed_name = name
        # 以下はどれもファイルをオープンしっぱなしになるもよう
        # self.__path = msg.get_filenames()
        # self.__msg = msg                               # msg_p
        # self.__thread = thread                         # thread_p

    def __del__(self):  # デストラクタ←本当に必要か不明
        del self

    # データ取得関数
    # def get_newest_date(self): return self.__newest_date

    # def get_path(self): return self.get_filenames() ←このデータは msg データ自身でないので当然駄目

    def get_message_id(self): return self._msg_id

    def get_list(self):
        list = ''
        for item in DISPLAY_ITEM:
            if item == 'date':
                list += self.__reformed_date+'\t'
            elif item == 'subject':
                subject = self.__thrd_depth * \
                    (' '+'\t')+self.__reformed_subject
                if item != DISPLAY_ITEM[-1]:  # 最後でない時は長さを揃えるために空白で埋める
                    list += str_just_length(subject, SUBJECT_LENGTH)+'\t'
                else:
                    list += subject+'\t'
            elif item == 'from':
                if item != DISPLAY_ITEM[-1]:  # 最後でない時は長さを揃えるために空白で埋める
                    list += str_just_length(
                            RE_TAB2SPACE.sub(' ', self.__reformed_name), FROM_LENGTH)+'\t'
                else:
                    list += RE_TAB2SPACE.sub(
                            ' ', RE_END_SPACE.sub('', self.__reformed_name))+'\t'
            else:
                print_err("Don't add '"+item+"' element in threa list.")
        return RE_END_SPACE.sub('', list)

    def get_date(self): return self.__reformed_date

    def get_subject(self): return self.__subject


def initialize():
    if 'DBASE' in globals():
        return
    global PATH, ATTACH_DIR, TEMP_DIR, DBASE
    PATH = get_config('database.path')
    if not os.path.isdir(PATH):
        print_error('\'' + PATH + '\' don\'t exist.')
        return
    if not notmuch_new(True):
        print_error('Can\'t update database.')
        return
    else:  # notmuch new の結果をクリア←redraw しないとメッセージが表示されるので、続けるためにリターンが必要
        if VIM_MODULE:
            vim.command('redraw')
    make_dir(ATTACH_DIR)
    make_dir(TEMP_DIR)
    rm_file(ATTACH_DIR)
    rm_file(TEMP_DIR)
    DBASE = notmuch.Database()
    DBASE.close()


def make_dir(dirname):
    if not os.path.isdir(dirname):
        os.mkdir(dirname)
        os.chmod(dirname, 0o700)


def notmuch_new(open_check):
    # メールを開いているとスワップファイルが有るので、データベースの再作成に失敗する
    # →open_check が True なら未保存バッファが有れば、そちらに移動し無ければバッファを完全に閉じる
    if VIM_MODULE and open_check:
        if opened_mail():
            print_warring('Can\'t remake database.\rBecase open the file.')
            return False
        # return True
    return shellcmd_popen(['notmuch', 'new'])


def opened_mail():  # メールボックス内のファイルが開かれているか?
    # 未保存なら、そのバッファに移動/開き True を返す
    # 全て保存済みならバッファから削除し False を返す
    for info in vim.eval('getbufinfo()'):
        filename = info['name']
        if filename.startswith(PATH):
            if info['changed'] == '1':
                win_id = info['windows']
                if len(win_id):
                    win_id = win_id[0]
                    vim.command('call win_gotoid('+win_id+')')
                elif info['hidden']:
                    vim.command(vim.vars['notmuch_open_way']['edit'].decode()
                                + ' ' + filename)
                return True
            vim.command('bwipeout '+info['bufnr'])
    return False


def shellcmd_popen(param):
    ret = run(param, stdout=PIPE, stderr=PIPE)
    # Notmuch run find $HOME/Mail/.backup/new/ -type f | xargs grep -l id: | xargs -I{} cp {} path:
    # で期待通りの動きをしなかった
    if ret.returncode:
        print_err(ret.stderr.decode('utf-8'))
        return False
    print(ret.stdout.decode('utf-8'))
    return True


# def make_thread_core_single(search_term):  # ダミー名
def make_thread_core(search_term):
    try:  # seach_term チェック
        notmuch.Query(DBASE, search_term).count_messages()
    except notmuch.errors.XapianError:
        THREAD_LISTS[search_term] = []
        print_error('notmuch.errors.XapianError: Check search term: ' + search_term + '.')
        return False
    if VIM_MODULE:
        reprint_folder()  # 新規メールなどでメール数が変化していることが有るので、フォルダ・リストはいつも作り直す
    threadlist = []
    query = notmuch.Query(DBASE, search_term)
    # 古い順にソート→新しい場合:NEWEST_FIRST
    query.set_sort(notmuch.Query.SORT.OLDEST_FIRST)
    try:  # スレッド一覧
        threads = query.search_threads()
    except notmuch.errors.NullPointerError:
        print_err('Error: Search thread')
    if VIM_MODULE:
        print('Making cache data:'+search_term)
    else:  # vim 以外では途中経過の表示なので標準出力ではなくエラー出力に
        sys.stderr.write('Making cache data: '+search_term+'\n')
    for thread in threads:
        qery = notmuch.Query(
            DBASE, '('+search_term+') and thread:'+thread.get_thread_id())
        # qery.set_sort(notmuch.Query.SORT.OLDEST_FIRST)  # スレッド内は常に古い順で OK
        try:  # スレッドの深さを調べる為のリスト作成開始 (search_term に合致しないメッセージも含まれる)
            msgs = thread.get_toplevel_messages()
        except notmuch.errors.NullPointerError:
            print_err('Error: get toplevel message')
        replies = []
        for msg in msgs:
            make_reply_ls(replies, msg, 0)
        # new version
        order = 0
        for reply in replies:
            try:  # 同一スレッドでsearch_termに合致するメッセージ一覧作成開始
                msgs = qery.search_messages()  # for の外/前にやると落ちる
            except notmuch.errors.NullPointerError:
                print_err('Error: Search message')
            for msg in msgs:
                if reply[0] == msg.get_message_id():
                    depth = reply[1]
                    if depth > order:
                        depth = order
                    threadlist.append(MailData(msg, thread, order, depth))
                    order = order+1
                    break
    threadlist.sort(key=attrgetter('_newest_date'))
    THREAD_LISTS[search_term] = threadlist
    if VIM_MODULE:
        vim.command('redraw')
    return True


# def make_thread_core(search_term):  # 作りかけ
def make_thread_core_multi(search_term):  # 作りかけ
    if VIM_MODULE:
        reprint_folder()  # 新規メールなどでメール数が変化していることが有るので、フォルダ・リストはいつも作り直す
    query = notmuch.Query(DBASE, search_term)
    # 古い順にソート→新しい場合:NEWEST_FIRST
    query.set_sort(notmuch.Query.SORT.OLDEST_FIRST)
    try:  # スレッド一覧
        threads = query.search_threads()
    except notmuch.errors.NullPointerError:
        print_err('Error: Search thread')
    if VIM_MODULE:
        print('Making cache data:'+search_term)
    else:  # vim 以外では途中経過の表示なので標準出力ではなくエラー出力に
        sys.stderr.write('Making cache data: '+search_term+'\n')
    with concurrent.futures.ThreadPoolExecutor() as executor:
        # param = map(lambda _: (threads, search_term), len(threads))
        # ls = executor.map(make_single_thread, param)
        f = [executor.submit(make_single_thread, i, search_term) for i in threads]
        ls = [r.result() for r in f]
    ls.sort(key=attrgetter('_newest_date'))
    THREAD_LISTS[search_term] = ls
    if VIM_MODULE:
        vim.command('redraw')


def make_single_thread(thread, search_term):
    qery = notmuch.Query(
        DBASE, '('+search_term+') and thread:'+thread.get_thread_id())
    # qery.set_sort(notmuch.Query.SORT.OLDEST_FIRST)  # スレッド内は常に古い順で OK
    try:  # スレッドの深さを調べる為のリスト作成開始 (search_term に合致しないメッセージも含まれる)
        msgs = thread.get_toplevel_messages()
    except notmuch.errors.NullPointerError:
        print_err('Error: get toplevel message')
    replies = []
    for msg in msgs:
        make_reply_ls(replies, msg, 0)
    # new version
    order = 0
    ls = []
    for reply in replies:
        try:  # 同一スレッドでsearch_termに合致するメッセージ一覧作成開始
            msgs = qery.search_messages()  # for の外/前にやると落ちる
        except notmuch.errors.NullPointerError:
            print_err('Error: Search message')
        for msg in msgs:
            if reply[0] == msg.get_message_id():
                depth = reply[1]
                if depth > order:
                    depth = order
                ls.append(MailData(msg, thread, order, depth))
                order = order+1
                break
    return ls


def make_reply_ls(ls, message, depth):  # スレッド・ツリーの深さ情報取得
    # new version
    ls.append((message.get_message_id(), depth))
    msgs = message.get_replies()
    for msg in msgs:
        make_reply_ls(ls, msg, depth+1)


def set_folder_format():
    global FOLDER_FORMAT
    try:
        DBASE.open(PATH)
    except NameError:
        return False
    a = len(str(int(notmuch.Query(DBASE, 'path:**').count_messages() * 1.2)))  # メール総数
    u = len(str(int(notmuch.Query(DBASE, 'tag:unread').count_messages())))+1
    f = len(str(int(notmuch.Query(DBASE, 'tag:flagged').count_messages())))+1
    # 末尾付近の↑ * 1.2 や + 1 は増加したときのために余裕を見ておく為
    max_len = 0
    for s in vim.vars['notmuch_folders']:
        s_len = len(s[0].decode())
        if s_len > max_len:
            max_len = s_len
    vim.command('call s:set_open_way(' + str(max_len + a + u + f + 5) + ')')
    FOLDER_FORMAT = '{0:<' + str(max_len) + '} {1:>' + str(u) + '}/{2:>' + \
        str(a) + '}|{3:>' + str(f) + '} [{4}]'
    DBASE.close()
    return True


def format_folder(folder, search_term):
    global FOLDER_FORMAT
    if not ('FOLDER_FORMAT' in globals()):
        FOLDER_FORMAT = '{0:<14}{1:>3}/{2:>5}|{3:>3} [{4}]'
    try:  # seach_term チェック
        all_mail = notmuch.Query(DBASE, search_term).count_messages()  # メール総数
    except notmuch.errors.XapianError:
        print_error('notmuch.errors.XapianError: Check search term: ' + search_term)
        vim.command('message')  # 起動時のエラーなので、再度表示させる
        return '\'search term\' (' + search_term + ') error'
    return FOLDER_FORMAT.format(
        folder,         # 擬似的なフォルダー・ツリー
        notmuch.Query(  # 未読メール数
            DBASE, '('+search_term+') and tag:unread').count_messages(),
        all_mail,
        notmuch.Query(  # 重要メール数
            DBASE, '('+search_term+') and tag:flagged').count_messages(),
        search_term     # 検索方法
    )


def print_folder():  # vim から呼び出された時にフォルダ・リストを書き出し
    try:
        DBASE.open(PATH)
    except NameError:
        return
    b = vim.buffers[vim.bindeval('s:buf_num')['folders']]
    b.options['modifiable'] = 1
    b[:] = None
    for folder_way in vim.vars['notmuch_folders']:
        folder = folder_way[0].decode()
        search_term = folder_way[1].decode()
        if search_term == '':
            b.append(folder)
        else:
            b.append(format_folder(folder, search_term))
    del b[0]
    b.options['modifiable'] = 0
    set_folder_b_vars(b.vars)
    DBASE.close()
    # vim.command('redraw')


def reprint_folder():
    # フォルダ・リストの再描画 (print_folder() の処理と似ているが、b[:] = None して書き直すとカーソル位置が変わる)
    b = vim.buffers[vim.bindeval('s:buf_num')['folders']]
    b.options['modifiable'] = 1
    for i, folder_way in enumerate(vim.vars['notmuch_folders']):
        folder = folder_way[0].decode()
        search_term = folder_way[1].decode()
        if search_term != '':
            b[i] = format_folder(folder, search_term)
    b.options['modifiable'] = 0
    set_folder_b_vars(b.vars)
    vim.command('redrawstatus!')


def set_folder_b_vars(v):  # フォルダ・リストのバッファ変数セット
    v['all_mail'] = notmuch.Query(DBASE, '').count_messages()
    v['unread_mail'] = notmuch.Query(DBASE, 'tag:unread').count_messages()
    v['flag_mail'] = notmuch.Query(DBASE, 'tag:flagged').count_messages()


def rm_file(dirname):  # 添付ファイル処理で作成したファイルやディレクトリ削除
    rm_file_core(dirname+'*'+os.sep+'*'+os.sep+'.*')
    rm_file_core(dirname+'*'+os.sep+'*'+os.sep+'*')
    rm_file_core(dirname+'*'+os.sep+'.*')
    rm_file_core(dirname+'*'+os.sep+'*')
    rm_file_core(dirname+'.*')
    rm_file_core(dirname+'*')


def rm_file_core(files):
    for name in glob.glob(files):
        if os.path.isfile(name):
            os.remove(name)
        else:
            os.rmdir(name)


def print_thread_view(search_term):  # vim 外からの呼び出し時のスレッド・リスト書き出し
    DBASE.open(PATH)
    if not make_thread_core(search_term):
        return False
    DBASE.close()
    for msg in THREAD_LISTS[search_term]:
        print(msg.get_list())
    return True


def get_unread_in_THREAD_LISTS(search_term):  # THREAD_LISTS から未読を探す
    return [i for i, x in enumerate(THREAD_LISTS[search_term])
            if ('unread' in DBASE.find_message(x.get_message_id()).get_tags())]


def open_thread(line, select_unread, remake):  # フォルダ・リストからスレッドリストを開く
    folder, search_term = vim.vars['notmuch_folders'][line - 1]
    folder = folder.decode()
    search_term = search_term.decode()
    b_num = vim.bindeval('s:buf_num')['thread']
    if folder == '':
        vim.command('call sign_unplace("mark_thread", {"name": "notmuch", "buffer": ' + str(b_num) + ', })')
        b = vim.buffers[b_num]
        b.options['modifiable'] = 1
        b[:] = None
        b.options['modifiable'] = 0
        b.vars['search_term'] = ''
        b.vars['tags'] = ''
        b.vars['pgp_result'] = ''
        return
    if search_term == '':
        vim.command('call win_gotoid(bufwinid(s:buf_num["folders"]))')
        notmuch_search([])
    if vim.bindeval('win_gotoid(bufwinid(' + str(b_num) + '))') \
            and not remake \
            and vim.current.buffer.vars['search_term'].decode() == search_term:
        return
    print_thread(b_num, search_term, select_unread, remake)


def print_thread(b_num, search_term, select_unread, remake):  # スレッド・リスト書き出し
    DBASE.open(PATH)
    print_thread_core(b_num, search_term, select_unread, remake)
    change_buffer_vars_core()
    DBASE.close()
    # vim.command('redraw!')


def print_thread_core(b_num, search_term, select_unread, remake):
    if search_term == '':
        return
    try:  # seach_term チェック
        unread = notmuch.Query(DBASE, search_term).count_messages()
    except notmuch.errors.XapianError:
        print_error('notmuch.errors.XapianError: Check search term: ' + search_term + '.')
        return
    # if vim.bindeval('win_getid(bufwinid(s:buf_num["thread"]))') == 0:
    #     reopen('thread', search_term)
    b = vim.buffers[b_num]
    vim.command('call sign_unplace("mark_thread", {"name": "notmuch", "buffer": ' + str(b_num) + ', })')
    b.vars['search_term'] = search_term
    if remake:
        make_thread_core(search_term)
        # THREAD_LISTS[search_term] = threadlist
        threadlist = THREAD_LISTS[search_term]
    else:
        try:
            threadlist = THREAD_LISTS[search_term]
        except KeyError:
            make_thread_core(search_term)
            threadlist = THREAD_LISTS[search_term]
    b.options['modifiable'] = 1
    b[:] = None
    for msg in threadlist:
        b.append(msg.get_list())
    del b[0]
    b.options['modifiable'] = 0
    print('Read data: ['+search_term+']')
    vim.command('call win_gotoid(bufwinid(' + str(b_num) + '))')
    if select_unread:
        index = get_unread_in_THREAD_LISTS(search_term)
        unread = notmuch.Query(
            DBASE, '('+search_term+') and tag:unread').count_messages()
        if len(index):
            index = index[0]
            vim.current.window.cursor = (index+1, 0)
            vim.command('call s:fold_open()')
        elif unread:  # フォルダリストに未読はないが新規メールを受信していた場合
            print_thread_core(b_num, search_term, True, True)
        else:
            vim.command('normal! G')
            vim.command('call s:fold_open()')


def change_buffer_vars():  # スレッド・リストのバッファ変数更新
    DBASE.open(PATH)
    change_buffer_vars_core()
    DBASE.close()
    vim.command('redrawstatus!')


def change_buffer_vars_core():
    b_v = vim.current.buffer.vars
    b_v['pgp_result'] = ''
    if vim.current.buffer[0] == '':  # ←スレッドなので最初の行が空か見れば十分
        b_v['msg_id'] = ''
        b_v['subject'] = ''
        b_v['date'] = ''
        b_v['tags'] = ''
    else:
        msg = THREAD_LISTS[b_v['search_term'].decode()][vim.current.window.cursor[0]-1]
        msg_id = get_msg_id()
        b_v['msg_id'] = msg_id
        b_v['subject'] = msg.get_subject()
        b_v['date'] = msg.get_date()
        b_v['tags'] = get_msg_tags(DBASE.find_message(msg_id))


def vim_escape(s):  # Vim と文字列をやり取りする時に、' をエスケープする
    # return s.replace('\\', '\\\\').replace("'", "''")
    return s.replace("'", "''")


def is_same_tabpage(kind, search_term):
    # おそらく vim.current.tabpage.number と比較する必要はないけど win_id2tabwin() の仕様変更などが起きた時用に念の為
    if not ('buf_num' in vim.bindeval('s:')):
        return False
    if not (kind in vim.bindeval('s:buf_num')):
        return False
    if kind == 'folders' or kind == 'thread' or kind == 'show':
        return vim.bindeval('win_id2tabwin(bufwinid(s:buf_num["' +
                            kind + '"]))')[0] == vim.current.tabpage.number
    # kind == search or view
    elif search_term == '':
        return False
    else:
        if not (search_term in vim.bindeval('s:buf_num')[kind]):
            return False
        return vim.bindeval('win_id2tabwin(bufwinid(' +
                            str(vim.bindeval('s:buf_num')[kind][search_term]) +
                            '))')[0] == vim.current.tabpage.number


def reload_show():
    b = vim.current.buffer
    print('reload', b.options['filetype'].decode()[8:])
    DBASE.open(PATH)
    open_mail_by_msgid(b.vars['search_term'].decode(),
                       b.vars['msg_id'].decode(), str(b.number), True)
    DBASE.close()


def reload_thread():
    if opened_mail():
        print_warring('Please save and close mail.')
        return
    b = vim.current.buffer
    search_term = b.vars['search_term'].decode()
    notmuch_new(False)
    w = vim.current.window
    # 再作成後に同じメールを開くため Messag-ID を取得しておく
    msg_id = get_msg_id()
    DBASE.open(PATH)  # ここで書き込み権限 ON+関数内で OPEN のままにしたいが、そうすると空のスレッドで上の
    # search_term = b.vars['search_term'].decode()
    # で固まる
    print_thread_core(b.number, search_term, False, True)
    if msg_id != '':
        index = [i for i, msg in enumerate(
            THREAD_LISTS[search_term]) if msg.get_message_id() == msg_id]
    # else:  # 開いていれば notmuch-show を一旦空に←同一タブページの時は vim script 側メールを開くので不要
    # ただし、この関数内でその処理をすると既読にしてしまいかねないので、ここや print_thread() ではやらない
    if b[0] == '':  # リロードの結果からのスレッド空←スレッドなので最初の行が空か見れば十分
        if 'show' in vim.bindeval('s:buf_num'):
            empty_show()
        return
    # ウィンドウ下部にできるだけ空間表示がない様にする為一度最後のメールに移動後にウィンドウ最下部にして表示
    # w.cursor = (vim.bindeval('line("$")'), 0)
    # vim.command('normal! z-')
    vim.command('normal! Gz-')
    if msg_id != '' and len(index):  # 実行前のメールがリストに有れば選び直し
        w.cursor = (index[0]+1, 0)
    else:
        print('Don\'t select same mail.\nBecase already Delete/Move/Change folder/tag.')
    change_buffer_vars_core()
    DBASE.close()
    if b[0] != '':
        vim.command('call s:fold_open()')
        if is_same_tabpage('show', ''):
            # タグを変更することが有るので書き込み権限も
            DBASE.open(PATH, mode=notmuch.Database.MODE.READ_WRITE)
            open_mail_by_msgid(
                    search_term,
                    THREAD_LISTS[search_term][w.cursor[0] - 1].get_message_id(),
                    str(b.number), False)
            DBASE.close()


def reopen(kind, search_term):  # スレッド・リスト、メール・ヴューを開き直す
    if kind == 'search':  # or kind == 'view':
        search_term = search_term.decode()
    vim.command('call s:change_exist_tabpage("' + kind + '", \'' + vim_escape(search_term) + '\')')
    # 他のタプページにもなかった
    if kind == 'search' or kind == 'view':
        buf_num = vim.eval('s:buf_num')[kind][search_term]
    else:
        buf_num = vim.eval('s:buf_num')[kind]
    if vim.bindeval('win_gotoid(bufwinid(' + buf_num + '))') == 0:
        if kind == 'thread':
            vim.command('call win_gotoid(bufwinid(s:buf_num["folders"])) | silent only')
        open_way = vim.vars['notmuch_open_way'][kind].decode()
        if open_way == 'enew':
            vim.command('silent buffer '+buf_num)
        if open_way == 'tabedit':
            vim.command('silent tab sbuffer '+buf_num)
        else:
            open_way = re.sub(r'\bnew\b',       'split',     open_way)
            open_way = re.sub(r'([0-9])new\b',  '\\1split',  open_way)
            open_way = re.sub(r'\bvnew\b',      'vsplit',    open_way)
            open_way = re.sub(r'([0-9])vnew\b', '\\1vsplit', open_way)
            vim.command(open_way)
            vim.command('silent buffer '+buf_num)
        if kind == 'thread':
            open_way = vim.vars['notmuch_open_way']['show'].decode()
            if open_way != 'enew' and open_way != 'tabedit':
                vim.command('call s:make_show()')
        elif kind == 'search':
            open_way = vim.vars['notmuch_open_way']['view'].decode()
            if open_way != 'enew' and open_way != 'tabedit':
                vim.command('call s:make_view(\'' + vim_escape(search_term) + '\')')
        vim.command('call win_gotoid(bufwinid(' + buf_num + '))')


def open_mail(search_term, index, active_win):  # 実際にメールを表示
    # タグを変更することが有るので書き込み権限も
    DBASE.open(PATH, mode=notmuch.Database.MODE.READ_WRITE)
    threadlist = THREAD_LISTS[search_term]
    msg_id = threadlist[index].get_message_id()
    open_mail_by_msgid(search_term, msg_id, active_win, False)
    DBASE.close()


def open_mail_by_msgid(search_term, msg_id, active_win, mail_reload):
    # スレッド・リストの順番ではなく Message_ID によってメールを開く
    # 開く前に呼び出し元となるバッファ変数保存
    def check_end_view():  # メール終端まで表示しているか?
        if vim.bindeval('line("w$")') == vim.bindeval('line("$")'):  # 末尾まで表示
            # ただしメールなので、行が長く折り返されて表示先頭行と最終行が同一の場合は考慮せず
            return True
        else:
            return False

    def get_msg():  # 条件を満たす Message とそのメール・ファイル名を取得
        # ファイルが全て消されている場合は、None, None を返す
        b_v['search_term'] = search_term
        msg = list(notmuch.Query(
            DBASE, '('+search_term+') and id:'+msg_id).search_messages())
        if len(msg):
            msg = list(msg)[0]
        else:  # 同一条件+Message_ID で見つからなくなっているので Message_ID だけで検索
            print('Already Delete/Move/Change folder/tag')
            msg = DBASE.find_message(msg_id)
            if msg is None:
                b_v['msg_id'] = ''
                b_v['subject'] = ''
                b_v['date'] = ''
                b_v['tags'] = ''
                return None, None
        reindex = False
        b_v['msg_id'] = msg_id
        b_v['subject'] = msg.get_header('Subject')
        b_v['date'] = msg.get_date()
        b_v['tags'] = get_msg_tags(msg)
        if active_win != vim.current.window.number \
                and (is_same_tabpage('thread', '') or is_same_tabpage('search', search_term)):
            thread_b_v['msg_id'] = msg_id
            thread_b_v['subject'] = b_v['subject']
            thread_b_v['date'] = b_v['date']
            thread_b_v['tags'] = b_v['tags']
        for f in msg.get_filenames():
            if os.path.isfile(f):
                if reindex:
                    DBASE.close()
                    reindex_mail(msg_id, '', '')
                    msg = DBASE.find_message(msg_id)
                    DBASE.open(PATH, mode=notmuch.Database.MODE.READ_WRITE)
                return msg, f
            reindex = True  # メール・ファイルが存在しなかったので、再インデックスが必要
            # やらないとデータベース上に残る存在しないファイルからの情報取得でエラー発生

    def print_header(notmuch_headers):  # vim からの呼び出し時に msg 中の notmuch_headers のリストに有るヘッダ出力
        # (何故か Content-Type, Content-Transfer-Encoding は取得できない)
        b = vim.current.buffer
        for header in notmuch_headers:
            header = header.decode()
            line = msg.get_header(header)
            if line != '':
                line = line.replace('\t', ' ')
                if header.lower() == 'message-id':
                    line = header+': <'+line+'>'
                else:
                    line = header+': '+line
                b.append(line)
                if vim.current.window.width*2 < vim.strwidth(line):
                    n = vim.eval('line("$")')
                    vim.command(n+','+n+'fold')

    def print_virtual_header(header):
        attachments = msg_file.get_all(header)
        if attachments is None:
            return
        b = vim.current.buffer
        for f in attachments:
            f = get_attach_name(f)
            f = os.path.expandvars(re.sub('^~/', '$HOME/', f))
            if os.sep == '\\':  # Windows の場合
                match = re.match(r'^.+\\', f)
                if match is None:  # パスが / 区切りの場合も確認
                    match = re.match('^.+/', f)
            else:
                match = re.match('^.+/', f)
            if match is None:  # フル・パスでないので送信メールでなくメール本文を単純にテキスト・ファイルとして保存し、それをインポートしたファイル
                name = f
                tmp_dir = ''
            else:
                name = f[match.end():]
                tmp_dir = f[:match.end()]
            if os.path.isfile(f):
                header = 'Attach: '
                b_attachments[vim.eval('line("$")')] = [name, -1, tmp_dir]
            else:
                header = 'Del-Attach: '
            b.append(header+name)

    def vim_append_content(s):  # 複数行を vim のカレントバッファに書き込み
        # splitlines() だと、以下全てが区切り文字の対象
        # \n:         改行
        # \r:         復帰
        # \r\n:       改行+復帰
        # \v or \x0b: 垂直タブ
        # \f or \x0c: 改ページ
        # \x1c:       ファイル区切り
        # \x1d:       グループ区切り
        # \x1e:       レコード区切り
        # \x85:       改行 (C1 制御コード)
        # \u2028:     行区切り
        # \u2029:     段落区切り
        b = vim.current.buffer
        s = re.sub('[\u200B-\u200D\uFEFF]', '', s)  # ゼロ幅文字の削除
        b.append(re.split('[\n\r\v\x0b\x1d\x1e\x85\u2028\u2029]',
                          s.replace('\r\n', '\n').replace('\x1c', '\f')))
        while b[-1] == '':
            b[-1] = None

    def get_mail_context(part, charset, encoding):  # メールの本文をデコードして取り出す
        if encoding == '8bit':
            return part.get_payload()
        else:
            try:
                return part.get_payload(decode=True).decode(charset, 'ignore')
            except LookupError:
                print_warring('unknon encoding ' + charset + '.')
                return part.get_payload()

    def print_attach_header(header, name):
        # 添付ファイル削除の有無を調べる もっと効率よい方法はないものか?
        for delete_header in part.keys():  # ヘッダー部を全て削除
            part.__delitem__(delete_header)
        if len(part.as_string()) > 1:  # 中身が残っているので添付ファイル未削除
            b_attachments[vim.eval('line("$")')] = [name, part_num, '']
        else:
            header = 'Del-' + header
        vim.current.buffer.append(header+name)

    def add_attachment_list(part_num, pgp):  # 添付ファイルのリストに追加
        attachment = get_attach_name(part.get_filename())
        signature = ''
        inline = g_inline | is_inline(part)
        if pgp:
            header = 'Encrypt-File: '
            if inline:
                signature = part.get_payload()
        elif part.get_content_type().find('application/pgp-signature') != 0:
            header = 'Attach: '
        else:  # 電子署名の検証←やり方が解っていないので全て不正署名になってしまう
            # 取り敢えず署名未検証とする処理始まり
            print_attach_header('Signature: ', attachment)
            if inline:
                return '\n\n' + part.get_payload()
            else:
                return ''
            # 取り敢えず署名未検証とする処理終わり
            if shutil.which('gpg') is None:
                print_attach_header('Signature: ', attachment)
                if inline:
                    return '\n\n' + part.get_payload()
                else:
                    return ''
            make_dir(TEMP_DIR)
            pgp_tmp = TEMP_DIR + 'pgp.tmp'
            decrypt_tmp = TEMP_DIR + 'decrypt.tmp'
            with open(decrypt_tmp, 'w') as fp:
                fp.write(pre_part.get_payload(decode=False))
            with open(pgp_tmp, 'w') as fp:
                fp.write(part.get_payload(decode=False))
            ret = run(['gpg', '--verify', pgp_tmp, decrypt_tmp],
                      stdout=PIPE, stderr=PIPE)
            if ret.returncode:
                if ret.returncode == 1:
                    header = 'Bad-Signature: '
                else:
                    header = 'Signature: '
                if inline:  # Content-Disposition: inline では電子署名を本文に表示
                    signature = '\n\n' + part.get_payload()
            else:
                header = 'Good-Signature: '
            # rm_file(pgp_tmp)
            # rm_file(decrypt_tmp)
            set_pgp_result(b_v, thread_b_v, ret)
        print_attach_header(header, attachment)
        return signature

    def print_content(part, text, html, html_count):
        content_type = part.get_content_type()
        # メールを単純にファイル保存した時は UTF-8 にしているので、それをインポートしたときのため、仮の値として指定しておく
        charset = part.get_content_charset('utf-8')
        encoding = part.get('Content-Transfer-Encoding')
        if content_type.find('text/plain') == 0:
            tmp_text = re.sub(r'[\s\n]+$', '',  # 本文終端の空白削除
                              get_mail_context(part, charset, encoding))
            if tmp_text != '' and tmp_text != '\n':
                text += '\f'+tmp_text
        elif content_type.find('text/html') == 0:
            tmp_text = get_mail_context(part, charset, encoding)
            if tmp_text == '':
                if html_count:  # 2 個目以降があれば連番
                    b.append('Del-HTML: index'+str(html_count)+'.html')
                else:
                    b.append('Del-HTML: index.html')
            else:
                # 最適な設定が定まっていない
                html_converter = HTML2Text()
                # html_converter.table_start = True
                # html_converter.ignore_tables = True
                # html_converter.ignore_tables = True
                html_converter.body_width = len(tmp_text)
                html += '\f' + \
                    re.sub(r'[\s\n]+$', '', html_converter.handle(tmp_text))
                if html_count:  # 2 個目以降があれば連番
                    b_attachments[vim.eval('line("$")')] = \
                            ['index'+str(html_count)+'.html', part_num, '']
                    b.append('HTML: index'+str(html_count)+'.html')
                else:
                    b_attachments[vim.eval('line("$")')] = ['index.html', part_num, '']
                    b.append('HTML: index.html')
            html_count += 1
        else:
            text += add_attachment_list(part_num, False)
        return text, html, html_count

    def is_inline(part):
        disposition = part.get_all('Content-Disposition')
        if disposition is not None:
            for d in disposition:
                if type(d) != 'str':
                    continue
                if d.find('inline') != -1:
                    return True
        return False

    def set_pgp_result(b_v, thread_b_v, ret):
        result = ret.stdout.decode('utf-8') + '\n' + ret.stderr.decode('utf-8')
        b_v['pgp_result'] = result
        thread_b_v['pgp_result'] = result

    not_search = vim.current.buffer.number
    not_search = vim.bindeval('s:buf_num')['thread'] == not_search \
        or vim.bindeval('s:buf_num')['show'] == not_search
    if not_search:
        thread_b_v = vim.buffers[vim.bindeval('s:buf_num')['thread']].vars
    else:
        thread_b_v = vim.buffers[vim.bindeval('s:buf_num')['search'][search_term]].vars
    # :+17 に書いた通り、この方はうまくいかないケースが有る
    # subject = thread_b_v['subject']
    # date = thread_b_v['date']
    # tags = thread_b_v['tags']
    # 開く
    if not_search:
        vim.command('call s:make_show()')
    else:
        vim.command('call s:make_view(\'' + vim_escape(search_term) + '\')')
    b = vim.current.buffer
    b_v = b.vars
    if msg_id == '' or (mail_reload is False and msg_id == b_v['msg_id'].decode()):
        vim.command('call win_gotoid(bufwinid('+active_win+'))')
        return
    # 以下実際の描画
    b.options['modifiable'] = 1
    b[:] = None
    # 保存しておいたバッファ変数を開いたバッファに写す
    # ↑この↓の方法は、thread が非表示や show をアクティブで next_unread() が使われた時にうまく行かない
    # b_v['msg_id'] = msg_id
    # b_v['search_term'] = search_term
    # b_v['subject'] = subject
    # b_v['date'] = date
    # b_v['tags'] = tags
    msg, f = get_msg()
    if msg is None:
        b.append('Already all mail file delete.')
        del b[0]
        b.options['modifiable'] = 0
        vim.command('call win_gotoid(bufwinid('+active_win+'))')
        vim.command('redrawstatus!')
        return
    vim.options['guitabtooltip'] = 'tags['+get_msg_tags(msg)+']'
    print_header(vim.vars['notmuch_show_headers'])
    fold_begin = vim.bindeval('line("$")')  # 後から先頭行を削除するので予め
    print_header(vim.vars['notmuch_show_hide_headers'])
    b_attachments = {}  # vim でバッファ変数として保存しておく次の情報
    # * 添付ファイル名
    # * part番号
    # * 下書きをそのまま送信メールとした時のファイルの保存ディレクトリ
    # vim とやり取りするので辞書のキーは、行番号。item は tapple でなく list
    if fold_begin != vim.bindeval('line("$")'):
        vim.command(str(fold_begin+1)+','+vim.eval('line("$")')+'fold')
    with open(f, 'rb') as fp:
        msg_file = email.message_from_binary_file(fp)
    # 下書きをそのまま送信メールとした時の疑似ヘッダの印字
    header_line = vim.bindeval('line("$")')   # 疑似ヘッダ以外の印字終了
    print_virtual_header('X-Attach')
    print_virtual_header('Attach')
    content_text = ''  # 普通は本文が二重になっていることはないが念の為 content_text += hoge の形にしている
    content_html = ''
    html_count = 0       # text/html の個数
    b_v['notmuch_attachments'] = None
    b_v['pgp_result'] = ''
    part_num = -1
    pgp_encrypt = ''
    pre_part = None
    for part in msg_file.walk():
        part_num += 1
        if pgp_encrypt != '':
            if shutil.which('gpg') is None:
                content_text += add_attachment_list(-2, True)
                pgp_encrypt = ''
                continue
            make_dir(TEMP_DIR)
            rm_file(TEMP_DIR)
            pgp_tmp = TEMP_DIR + 'pgp.tmp'
            decrypt_tmp = TEMP_DIR + 'decrypt.tmp'
            with open(pgp_tmp, 'w') as fp:
                fp.write(part.get_payload(decode=False))
            ret = run(['gpg', '--yes', '--output', decrypt_tmp, '--decrypt', pgp_tmp],
                      stdout=PIPE, stderr=PIPE)
            set_pgp_result(b_v, thread_b_v, ret)
            if ret.returncode <= 1:  # ret.returncode == 1 は署名検証失敗でも復号化はできている可能性あり
                with open(decrypt_tmp, 'rb') as fp:
                    decrypt_msg = email.message_from_binary_file(fp)
                    content_text, content_html, html_count = print_content(
                            decrypt_msg, content_text, content_html, html_count)
                b.append('PGP-Decrypted: ' + pgp_encrypt)
            if ret.returncode:  # 署名未検証/失敗は ret.returncode >= 1 なので else/elif ではだめ
                if ret.returncode == 1:
                    b.append('Bad-Signature: ' + pgp_encrypt)
                else:
                    b.append('PGP-Encrypted: ' + pgp_encrypt)
                content_text += add_attachment_list(-2, True)
            pgp_encrypt = ''
            rm_file(pgp_tmp)
            rm_file(decrypt_tmp)
            continue
        if part.is_multipart():
            g_inline = is_inline(part)
            part_num -= 1
            continue
        if part.get_content_disposition() == 'attachment':  # 先に判定しないと、テキストや HTML ファイルが本文扱いになる
            if part.get_content_type().find('application/pgp-encrypted') == 0:
                pgp_encrypt = get_mail_context(part, 'utf-8', '')
                continue
            else:
                content_text += add_attachment_list(part_num, False)
        else:
            content_text, content_html, html_count = \
                print_content(part, content_text, content_html, html_count)
        pre_part = part  # 電子署名は直前の part との比較になる
    b.append('')  # ヘッダと本文区切り
    if content_text != '':
        vim_append_content(content_text[1:])
    if content_html != '':
        fold_begin = vim.bindeval('line("$")')  # text/plain がある時は折りたたむので開始行記録
        vim_append_content(content_html[1:])
        if content_text != '':  # 実際に折りたたむ場合
            b.append('\fHTML part\f', fold_begin)
            vim.command(str(fold_begin+1)+','+vim.eval('line("$")')+'fold')
    del b[0]
    b.options['modifiable'] = 0
    if header_line == vim.bindeval('line("$")'):  # 本文空
        header_line = 1
    elif b_attachments == {}:
        header_line = header_line + 1
    b_v['notmuch_attachments'] = b_attachments
    vim.current.window.cursor = (1, 0)  # カーソル位置が画面内だと先頭が表示されない
    vim.command('redraw')  # 本当は redrawstatus の位置にしたいが、上が効かなくなる
    vim.current.window.cursor = (header_line, 0)  # カーソルを添付ファイルや本文位置にセット
    if check_end_view() and ('unread' in msg.get_tags()):
        msg = change_tags_before_core(msg.get_message_id())
        delete_msg_tags(msg, ['unread'])
        change_tags_after_core(msg, True)
    vim.command('call win_gotoid(bufwinid('+active_win+'))')
    vim.command('redrawstatus!')


def empty_show():
    b = vim.buffers[vim.bindeval('s:buf_num')['show']]
    b.options['modifiable'] = 1
    b[:] = None
    b.options['modifiable'] = 0
    b_v = b.vars
    b_v['msg_id'] = ''
    b_v['search_term'] = ''
    b_v['subject'] = ''
    b_v['date'] = ''
    b_v['tags'] = ''
    b_v['pgp_result'] = ''
    vim.command('redrawstatus!')


def get_msg_id():  # notmuch-thread, notmuch-show で Message_ID 取得
    if not ('buf_num' in vim.bindeval('s:')):  # Notmuch mail-new がいきなり呼び出された時
        return ''
    b = vim.current.buffer
    bufnr = b.number
    if bufnr == vim.bindeval('s:buf_num')['folders'] or vim.current.buffer[0] == '':
        # ↑notmuch-folder に加えて、その以外の notmuch-??? は最初の行が空なら全体が空
        return ''
    try:
        search_term = b.vars['search_term'].decode()
    except KeyError:
        return ''
    if search_term == '':  # search_term が空ならスレッドやメール本文を開いていない
        return ''
    if ('show' in vim.bindeval('s:buf_num')
        and bufnr == vim.bindeval('s:buf_num')['show']) \
        or (search_term in vim.bindeval('s:buf_num')['view']
            and bufnr == vim.bindeval('s:buf_num')['view'][search_term]):
        return b.vars['msg_id'].decode()
    elif bufnr == vim.bindeval('s:buf_num')['thread'] \
        or (search_term in vim.bindeval('s:buf_num')['search']
            and bufnr == vim.bindeval('s:buf_num')['search'][search_term]):
        return THREAD_LISTS[search_term][vim.current.window.cursor[0]-1].get_message_id()
    return ''


def change_tags_before(msg_id):  # タグ変更前の前処理
    DBASE.open(PATH, mode=notmuch.Database.MODE.READ_WRITE)
    return change_tags_before_core(msg_id)


def change_tags_before_core(msg_id):
    msg = DBASE.find_message(msg_id)
    if msg is None:
        print_err('Message-ID: ' + msg_id + ' don\'t find.\nDatabase is broken or emails have been deleted.')
    msg.freeze()
    return msg


def get_msg_all_tags_list(tmp):  # データベースで使われている全て+notmuch 標準のソート済みタグのリスト
    DBASE.open(PATH)
    tag = get_msg_all_tags_list_core()
    DBASE.close()
    return tag


def get_msg_all_tags_list_core():
    tags = []
    for tag in DBASE.get_all_tags():
        tags.append(tag)
    tags += ['flagged', 'inbox', 'passed', 'replied', 'unread', 'Trash', 'Spam']
    tags = list(set(tags))
    tags = sorted(tags, key=str.lower)
    return tags


def get_msg_tags(msg):  # メールのタグ一覧の文字列表現
    if msg is None:
        return ''
    return ' '.join(msg.get_tags())


def add_msg_tags(msg, tags):  # メールのタグ追加→フォルダ・リスト書き換え
    try:  # 同一 Messag-ID の複数ファイルの移動で起きるエラー対処 (大抵移動は出来ている)
        for tag in tags:
            msg.add_tag(tag, sync_maildir_flags=True)
    except notmuch.NotInitializedError:
        pass


def delete_msg_tags(msg, tags):  # メールのタグ削除→フォルダ・リスト書き換え
    for tag in tags:
        msg.remove_tag(tag, sync_maildir_flags=True)


def add_tags(msg_id, s, args):  # vim から呼び出しで Message_ID を引数で渡さないヴァージョン
    tags = args[2:]
    if tags == []:
        tags = vim.eval('input("Add tag: ", "", "customlist,Complete_add_tag_input")')
        tags = tags.split()
    if tags == [] or tags is None:
        return
    msg = change_tags_before(msg_id)
    add_msg_tags(msg, tags)
    change_tags_after(msg, True)
    return [0, 0] + tags


def delete_tags(msg_id, s, args):  # vim から呼び出しで Message_ID を引数で渡さないヴァージョン
    tags = args[2:]
    if tags == []:
        tags = vim.eval('input("Delete tag: ", "", "customlist,Complete_delete_tag_input")')
        tags = tags.split()
    if tags == [] or tags is None:
        return
    msg = change_tags_before(msg_id)
    delete_msg_tags(msg, tags)
    change_tags_after(msg, True)
    return [0, 0] + tags


def toggle_tags(msg_id, s, args):  # vim からの呼び出しで tag をトグル
    tags = args[2:]
    if tags == []:
        tags = vim.eval('input("Toggle tag: ", "", "customlist,Complete_tag_input")')
        tags = tags.split()
    if tags == []:
        return []
    msg = change_tags_before(msg_id)
    for tag in tags:
        if tag in msg.get_tags():
            delete_msg_tags(msg, [tag])
        else:
            add_msg_tags(msg, [tag])
    change_tags_after(msg, True)
    return [0, 0] + tags


def get_msg_tags_list(tmp):  # vim からの呼び出しでメールのタグをリストで取得
    msg_id = get_msg_id()
    if msg_id == '':
        return []
    DBASE.open(PATH)
    msg = DBASE.find_message(msg_id)
    tags = []
    for tag in msg.get_tags():
        tags.append(tag)
    DBASE.close()
    return sorted(tags, key=str.lower)


def get_msg_tags_diff(tmp):  # メールに含まれていないタグ取得
    msg_id = get_msg_id()
    if msg_id == '':
        return []
    DBASE.open(PATH)
    tags = get_msg_all_tags_list_core()
    msg = DBASE.find_message(msg_id)
    for tag in msg.get_tags():
        tags.remove(tag)
    DBASE.close()
    return sorted(tags, key=str.lower)


def get_search_snippet(word):  # word によって補完候補を切り替える
    snippet = []
    if word[0:7] == 'folder:':
        for v in get_mail_folders():
            snippet.append('folder:' + v)
    elif word[0:4] == 'tag:':
        for v in get_msg_all_tags_list(''):
            snippet.append('tag:' + v)
    else:
        return ['body:', 'from:', 'to:', 'subject:', 'attachment:',
                'mimetype:', 'tag:', 'id:', 'thread:', 'folder:', 'path:',
                'date:', 'lastmod:', 'query:', 'property:']
    return snippet


def change_tags_after(msg, change_b_tags):  # 追加/削除した時の後始末
    # change_b_tags: thread, show の b:tags を書き換えるか?
    # ↑インポート、送信時は書き換え不要
    change_tags_after_core(msg, change_b_tags)
    DBASE.close()


def change_tags_after_core(msg, change_b_tags):  # statusline に使っているバッファ変数の変更と notmuch-folder の更新
    msg.thaw()
    msg.tags_to_maildir_flags()
    msg_id = msg.get_message_id()
    if not VIM_MODULE:
        return
    if change_b_tags:
        tags = get_msg_tags(msg)
        for b in vim.buffers:
            if not b.options['filetype'].decode().startswith('notmuch-'):
                continue
            try:
                b_msg_id = b.vars['msg_id'].decode()
            except KeyError:  # notmuch-folder や空のバッファ
                continue
            if msg_id == b_msg_id:
                b.vars['tags'] = tags
    if 'folders' in vim.bindeval('s:buf_num'):
        reprint_folder()


def next_unread(active_win):  # 次の未読メッセージが有れば移動(表示した時全体を表示していれば既読になるがそれは戻せない)
    def open_mail_by_index(buf_num, index):
        vim.command('call win_gotoid(bufwinid(s:buf_num' + buf_num + '))')
        vim.current.window.cursor = (index+1, 0)
        vim.command('call s:fold_open()')
        if is_same_tabpage('show', '') or is_same_tabpage('view', search_term):
            open_mail_by_msgid(search_term,
                               THREAD_LISTS[search_term][index].get_message_id(),
                               active_win, False)
        DBASE.close()

    def seach_and_open_unread(index, search_term):
        # search_term の検索方法で未読が有れば、そのスレッド/メールを開く
        search_term = search_term.decode()
        if search_term == '' or not notmuch.Query(DBASE, '('+search_term+') and tag:unread').count_messages():
            vim.command('call win_gotoid(bufwinid('+active_win+'))')
            return False
        if vim.bindeval("win_gotoid(bufwinid(s:buf_num['folders']))"):
            vim.current.window.cursor = (index+1, 0)  # ここまではフォルダ・リストの順番としてindex使用
        b_num = vim.bindeval('s:buf_num')['thread']
        print_thread_core(b_num, search_term, False, False)
        # ここからはスレッド・リストの順番としてindex使用
        index = get_unread_in_THREAD_LISTS(search_term)
        try:
            index = index[0]
        except IndexError:  # THREAD_LISTS[search_term] 作成後に受信メールがある
            print_thread_core(b_num, search_term, False, True)
            index = get_unread_in_THREAD_LISTS(search_term)
            index = index[0]
        vim.current.window.cursor = (index+1, 0)
        vim.command('call s:fold_open()')
        change_buffer_vars_core()
        if is_same_tabpage('show', '') or is_same_tabpage('view', search_term):
            open_mail_by_msgid(search_term,
                               THREAD_LISTS[search_term][index].get_message_id(),
                               active_win, False)
        vim.command('call win_gotoid(bufwinid('+active_win+'))')
        DBASE.close()
        return True

    if not ('search_term' in vim.current.buffer.vars):
        if vim.current.buffer.number == vim.bindeval('s:buf_num')['folders']:
            msg_id = ''
            active_win = vim.bindeval('s:buf_num')['thread']
            search_term = vim.vars['notmuch_folders'][vim.current.window.cursor[0]-1][1]
        else:
            msg_id = get_msg_id()
            search_term = vim.vars['notmuch_folders'][0][1]
            # vim.bindeval('getbufinfo(s:buf_num["folders"])[0]["lnum"]')
            # は folders が非アクティブだと正確に取得できない
    else:
        msg_id = get_msg_id()
        search_term = vim.current.buffer.vars['search_term']
    search_term = search_term.decode()
    if is_same_tabpage('search', search_term) or is_same_tabpage('view', search_term):
        search_view = True  # 検索スレッドや検索ビューや否かのフラグ
        # vim.command('call win_gotoid(bufwinid(s:buf_num["view"][\\\'' + search_term + '\\\']))')
    else:
        search_view = False
        # vim.command('call win_gotoid(bufwinid(s:buf_num["show"]))')
    # タグを変更することが有るので、書き込み権限も
    DBASE.open(PATH, mode=notmuch.Database.MODE.READ_WRITE)
    if msg_id == '':  # 空のメール/スレッド、notmuch_folders から実行された場合
        # if search_view:  # そもそも検索にヒットしなければ、search, view は開かれないはず
        #     vim.command('call win_gotoid(bufwinid('+active_win+'))')
        #     return
        if vim.bindeval('win_getid(bufwinid(s:buf_num["thread"]))') == 0:
            reopen('thread', search_term)
        folders = vim.vars['notmuch_folders']
        for index, folder_way in enumerate(folders):  # まず search_term が何番目か
            if search_term == folder_way[1].decode():
                if search_term == '':
                    index = index+1
                    search_term = folders[index][1].decode()
                break
        for folder_way in folders[index:]:  # search_term 以降で未読が有るか?
            if seach_and_open_unread(index, folder_way[1]):
                return
            index = index+1
        for index, folder_way in enumerate(folders):  # 見つからなかったので最初から
            if seach_and_open_unread(index, folder_way[1]):
                return
        vim.command('call win_gotoid(bufwinid('+active_win+'))')
        DBASE.close()
        return
    index = [i for i, x in enumerate(
        THREAD_LISTS[search_term]) if x.get_message_id() == msg_id][0]
    indexes = get_unread_in_THREAD_LISTS(search_term)
    # ↑ len(indexes) > 0 なら未読有り
    index = [i for i, i in enumerate(indexes) if i > index]
    if len(index):  # 未読メールが同一スレッド内の後ろに有る
        if search_view:
            open_mail_by_index('["search"][\\\'' + search_term + '\\\']', index[0])
        else:
            open_mail_by_index('["thread"]', index[0])
        return
    # else:  # 同一スレッド内に未読メールが有っても後ろには無い
    #     pass
    # else:  # 同一スレッド内に未読がない、
    #     pass
    # 同一スレッド内に未読がない、または同一スレッド内に未読メールが有っても後ろには無い
    if search_view:  # search, view では先頭の未読に移動
        if len(indexes):
            open_mail_by_index('["search"][\\\'' + search_term + '\\\']', indexes[0])
        return
    folders = vim.vars['notmuch_folders']
    for index, folder_way in enumerate(folders):  # 同一検索方法までスキップ
        if search_term == folder_way[1].decode():
            break
    if index < len(folders):
        next_index = index+1  # 現在開いている検索条件の次から未読が有るか? を調べるのでカウント・アップ
        for folder_way in folders[next_index:]:
            if seach_and_open_unread(next_index, folder_way[1]):
                return
            next_index += 1
    # フォルダ・リストの最初から未読が有るか? を探し直す
    for index_refirst, folder_way in enumerate(folders[:index+1]):
        if seach_and_open_unread(index_refirst, folder_way[1]):
            return
    DBASE.close()


def reindex_mail(msg_id, s, args):
    shellcmd_popen(['notmuch', 'reindex', 'id:' + msg_id])


def get_attach_name(f):
    if f is None:  # ファイル名の記述がない
        return ''
    name = ''
    for string, charset in email.header.decode_header(f):
        if charset is None:
            if type(string) is bytes:
                name += string.decode('raw_unicode_escape')
            else:  # デコードされず bytes 型でないのでそのまま
                name += string
        elif charset == 'unknown-8bit':
            name += string.decode('utf-8')
        else:
            try:
                name += string.decode(charset)
            except UnicodeDecodeError:  # コード外範囲の文字が有る時のエラー
                print_warring('File name has out-of-code range characters.')
                # if charset.lower() == 'iso-2022-jp':  # 丸付き数字対応
                #     string = string.decode(charset, 'backslashreplace')
                #     for i in range(21, 41):
                #         string.replace(r'\x2d\x' + str(i), chr(9291+i))
                #         string.replace('\\x2d\\x' + str(i), chr(9291+i))
                #     name += string
                # else:
                #     name += string.decode(charset, 'backslashreplace')
                name += string.decode(charset, 'backslashreplace')
            except Exception:
                name += string.decode('raw_unicode_escape')
    return name.replace('\n', ' ')


def get_attach_info(line):
    b_v = vim.current.buffer.vars
    try:
        search_term = b_v['search_term'].decode()
    except KeyError:
        return None, None, None, None
    bufnr = vim.current.buffer.number
    if bufnr != vim.bindeval('s:buf_num')['show'] \
            and (not (search_term in vim.bindeval('s:buf_num')['view'])
                 or bufnr != vim.bindeval('s:buf_num')['view'][search_term]):
        return None, None, None, None
    line = str(line)
    b_attachments = b_v['notmuch_attachments']
    if line not in b_attachments:
        return None, None, None, None
    name, part_num, tmpdir = b_attachments[line]
    name = name.decode('utf-8')
    if name == '':  # 元々ファイル名情報がない場合
        name = 'nonename'
    if part_num == -1:
        return name, None, None, tmpdir.decode('utf-8')
    msg_id = b_v['msg_id'].decode()
    DBASE.open(PATH)
    msg = list(notmuch.Query(
        DBASE, '('+search_term+') id:'+msg_id).search_messages())
    if len(msg):
        msg = list(msg)[0]
    else:  # 同一条件+Message_ID で見つからなくなっているので Message_ID だけで検索
        print('Already Delete/Move/Change folder/tag')
        msg = DBASE.find_message(msg_id)
    with open(msg.get_filename(), 'rb') as fp:
        msg_file = email.message_from_binary_file(fp)
    DBASE.close()
    part_count = 0
    for attach in msg_file.walk():
        if attach.is_multipart():
            continue
        if part_num == part_count:
            break
        part_count += 1
    global ATTACH_DIR
    tmpdir = ATTACH_DIR + \
        sha256(vim.current.buffer.vars['msg_id']).hexdigest() + \
        os.sep+str(part_num)+os.sep
    # 添付ファイルでも Context-Type='text/plain' 等のテキストで、Content-Transfer-Encoding=8bit なら取り出し時にデコードの必要なし
    transfer_encoding = attach.get('Content-Transfer-Encoding')
    if transfer_encoding is None:
        decode = False
    else:
        decode = (attach.get_content_maintype().lower() == 'text'
                  and transfer_encoding.lower() == '8bit')
    return name, attach, decode, tmpdir


def open_attachment(args):  # vim で Attach/HTML: ヘッダのカーソル位置の添付ファイルを開く
    def same_attach(fname):
        fname = fname.decode('utf-8')
        for i, ls in vim.current.buffer.vars['notmuch_attachments'].items():
            name = ls[0].decode('utf-8')
            if fname == name:
                return get_attach_info(i.decode())
        return None, None, None, None

    args = [int(s) for s in args]
    for i in range(args[0], args[1]+1):
        filename, attachment, decode, full_path = get_attach_info(i)
        if filename is None:
            filename, attachment, decode, full_path = same_attach(vim.bindeval('expand("<cfile>>")'))
            if filename is None:
                if b'open' in vim.vars['notmuch_open_way'].keys():
                    vim.command(vim.vars['notmuch_open_way']['open'])
                return
        print('')  # もし下記の様な print_warning を出していればそれを消す
        if attachment is not None or decode is not None:
            if not os.path.isdir(full_path):
                os.makedirs(full_path)
                os.chmod(full_path, 0o700)
        elif full_path == '':  # attachment, decode が None
            # +保存ディレクトリが空なら送信メールでなくメール本文を単純にテキスト・ファイルとして保存し、それをインポートしたファイル
            print_warring('The header is vertulal.')
            return
        full_path += filename
        if not os.path.isfile(full_path):
            write_attach(attachment, decode, full_path)
        print('open '+filename)
        try:
            ret = run([vim.vars['notmuch_view_attachment'].decode(),
                      full_path], stdout=PIPE, stderr=PIPE, timeout=0.5)
            # timeout の指定がないと、アプリによって終了待ちになる
            if ret.returncode:
                print_warring(ret.stderr.decode('utf-8'))
        except TimeoutExpired:
            pass


def write_attach(attachment, decode, save_path):  # 添付ファイルを save_path に保存
    if decode:
        with open(save_path, 'w') as fp:
            fp.write(attachment.get_payload(decode=False))
    else:
        with open(save_path, 'wb') as fp:
            fp.write(attachment.get_payload(decode=True))


def save_attachment(args):  # vim で Attach/HTML: ヘッダのカーソル位置の添付ファイルを保存
    print('')  # もし print_warning を出していればそれを消す
    args = [int(s) for s in args[0:2]]
    for i in range(args[0], args[1]+1):
        filename, attachment, decode, full_path = get_attach_info(i)
        if filename is None:
            return
        elif attachment is None and decode is None:  # attachment, decode が None
            # →インポート/送信メールどちらであれ仮想ヘッダ添付ファイルの保存は意味がない
            print_warring('The header is vertulal.')
            return
        save_path = get_save_filename(get_save_dir() + filename)
        if save_path == '':
            return
        # 添付ファイルを開く時の一時的ディレクトリ full_path に同じファイルが有るか? 調べ、有ればそれを移動
        full_path += filename
        if os.path.isfile(full_path):
            shutil.move(full_path, save_path)
        else:
            write_attach(attachment, decode, save_path)
        vim.command('redraw')
        print('save '+save_path)


def delete_attachment(args):
    def get_modified_date_form():  # 削除したときに書き込む日付情報
        t = time.time()
        lt = datetime.datetime.fromisoformat(  # ローカル時間 (UTC 扱い形式) の ISO 8601 形式
            datetime.datetime.fromtimestamp(t).strftime('%Y-%m-%dT%H:%M:%S.000000'))
        utc = datetime.datetime.fromisoformat(  # UTC の ISO 8601 形式
            datetime.datetime.utcfromtimestamp(t).strftime('%Y-%m-%dT%H:%M:%S.000000'))
        t = (lt - utc).seconds / (60 * 60)   # ローカル時間と UTC の時差
        contry, code = locale.getlocale(locale.LC_TIME)
        locale.setlocale(locale.LC_TIME, 'C')
        m_time = datetime.datetime.now(datetime.timezone(
            datetime.timedelta(hours=t))).strftime('%a, %d %b %Y %H:%M %z')
        locale.setlocale(locale.LC_TIME, contry + '.' + code)
        return m_time

    def delete_attachment_core(part, m_time):
        # 添付ファイルの特定の part のみ削除 (削除後の内容は mutt を同じにしてある)
        if part.get_payload() == '':
            return False
        header = ''
        for key in part.keys():
            key_head = ''
            for h in part.get_all(key):
                key_head = key_head + h
            part.__delitem__(key)
            header += key + ': ' + key_head + '\n'
        c_header = 'message/external-body; access-type=x-mutt-deleted;\n' + \
            '\texpiration="' + m_time + '"; length=' + \
            str(len(re.sub(r'[\s\n]+$', '', part.get_payload())))
        part.__setitem__('Content-Type', c_header)
        part.set_payload(header)
        return True

    def delete_attachment_in_show(args):
        def delete_attachment_only_part(fname, part_num):  # part_num 番目の添付ファイルを削除
            with open(fname, 'r') as fp:
                msg_file = email.message_from_file(fp)
            i = 0
            for part in msg_file.walk():
                if part.is_multipart():
                    continue
                if part_num == i:
                    break
                i += 1
            if part_num != i:
                print_err('No exist ' + str(i) + ' part.')
                return
            m_time = get_modified_date_form()
            if delete_attachment_core(part, m_time):
                with open(fname, 'w') as fp:
                    fp.write(msg_file.as_string())
            return

        print('')  # print_warning を出していればそれを消す
        msg_id = get_msg_id()
        if msg_id == '':
            return
        DBASE.open(PATH, mode=notmuch.Database.MODE.READ_WRITE)
        args = [int(s) for s in args[0:2]]
        for i in range(args[0], args[1]+1):
            line = str(i)
            b = vim.current.buffer
            b_attachments = b.vars['notmuch_attachments']
            if line in b_attachments:
                tmp_name, part_num, tmpdir = b_attachments[line]
                if part_num == -1:
                    print_warring('The header is vertulal.')
                elif part_num == -2:
                    print_warring('This is encripted context.')
                else:
                    del b_attachments[line]
                    line = int(line)-1
                    if b[line].find('HTML:') == 0 and '\fHTML part\f' not in b[:]:
                        # HTML パートで text/plain が無ければ削除しない
                        print_warring('The mail is only HTML.')
                    else:
                        b.options['modifiable'] = 1
                        if b[line].find('HTML:') == 0:
                            for i, b_i in enumerate(b):
                                if b_i == '\fHTML part\f':
                                    break
                            b[i:] = None
                        b[line] = 'Del-' + b[line]
                        b.options['modifiable'] = 0
                        # メール本文表示だと未読→既読扱いでタグを変更することが有るので書き込み権限も
                        # DBASE.open(PATH)
                        msg = DBASE.find_message(msg_id)
                        for f in msg.get_filenames():
                            delete_attachment_only_part(f, part_num)
        DBASE.close()

    def delete_attachment_in_thread(args, search_term):
        # メール本文表示だと未読→既読扱いでタグを変更することが有るので書き込み権限も
        def delete_attachment_all(fname):  # text/plin, text/html 以外の全て添付ファイルを削除
            with open(fname, 'r') as fp:
                msg_file = email.message_from_file(fp)
            m_time = get_modified_date_form()
            deleted = False
            can_delete = True
            next_can_delete = True
            for part in msg_file.walk():
                if part.is_multipart():
                    continue
                content_type = part.get_content_type()
                if part.get_content_type().find('application/pgp-encrypted') == 0:
                    can_delete = False
                    next_can_delete = False
                else:  # 直前が application/pgp-encrypted だと application/oct stream でも削除しない
                    can_delete = next_can_delete
                    next_can_delete = True  # 次は削除して良い可能背有り
                if content_type.find('text/plain') != 0 \
                        and content_type.find('text/html') != 0 \
                        and can_delete:
                    deleted = deleted | delete_attachment_core(part, m_time)
            if deleted:
                with open(fname, 'w') as fp:
                    fp.write(msg_file.as_string())
            return

        DBASE.open(PATH, mode=notmuch.Database.MODE.READ_WRITE)
        args = [int(s) for s in args[0:2]]
        for i in range(args[0], args[1]+1):
            msg_id = THREAD_LISTS[search_term][i-1].get_message_id()
            msg = DBASE.find_message(msg_id)
            for f in msg.get_filenames():
                delete_attachment_all(f)
        DBASE.close()
        bnum = vim.current.buffer.number
        if bnum == vim.bindeval('s:buf_num')['thread'] \
                and is_same_tabpage('show', ''):
            b = vim.buffers[vim.bindeval('s:buf_num')['show']]
        elif bnum == vim.bindeval('s:buf_num')["search"][search_term] \
                and is_same_tabpage('view', search_term):
            b = vim.buffers[vim.bindeval('s:buf_num')["view"][search_term]]
        else:
            return
        b_attachments = b.vars['notmuch_attachments']
        b_v_keys = b_attachments.keys()
        b.options['modifiable'] = 1
        for k in b_v_keys:
            line = int(k.decode()) - 1
            if b_attachments[k][1] != -1 and b[line].find('Attach:') == 0:
                b[line] = 'Del-' + b[line]
                del b_attachments[k]
        b.options['modifiable'] = 0

    b = vim.current.buffer
    bufnr = b.number
    search_term = b.vars['search_term'].decode()
    if bufnr == vim.bindeval('s:buf_num')['show'] \
        or ((search_term in vim.bindeval('s:buf_num')['view'])
            and bufnr == vim.bindeval('s:buf_num')['view'][search_term]):
        delete_attachment_in_show(args)
    elif bufnr == vim.bindeval('s:buf_num')['thread'] \
        or ((search_term in vim.bindeval('s:buf_num')['search'])
            and bufnr == vim.bindeval('s:buf_num')['search'][search_term]):
        delete_attachment_in_thread(args, search_term)


def cut_thread(msg_id, dumy):
    if msg_id == '':
        msg_id = get_msg_id()
        if msg_id == '':
            return
    bufnr = vim.current.buffer.number
    if bufnr == vim.bindeval('s:buf_num')['folders']:
        return
    DBASE.open(PATH)
    msg = DBASE.find_message(msg_id)
    changed = False
    for f in msg.get_filenames():
        with open(f, 'r') as fp:
            msg_file = email.message_from_file(fp)
        in_reply = msg_file.__getitem__('In-Reply-To')
        if in_reply is None:
            continue
        in_reply = in_reply.__str__()[1:-1]
        changed = True
        msg_file.__delitem__('In-Reply-To')
        ref_all = ''
        refs = msg_file.get_all('References')
        if refs is not None:
            for ref in refs:
                ref_all += ref
            ref_all = re.sub(r'(\n|\r|\s)*<?' + in_reply + '>?', '', ref_all)
            ref_all = re.sub(r'(\n|\r|\s)+$', '', ref_all)
        if ref_all == '':
            msg_file.__delitem__('References')
        else:
            msg_file.replace_header('References', ref_all)
        with open(f, 'w') as fp:
            fp.write(msg_file.as_string())
    DBASE.close()
    if changed:
        shellcmd_popen(['notmuch', 'reindex', 'id:' + msg_id])
        search_term = vim.current.buffer.vars['search_term'].decode()
        print_thread(bufnr, search_term, False, True)
        index = [i for i, x in enumerate(
            THREAD_LISTS[search_term]) if x.get_message_id() == msg_id]
        if len(index):
            vim.current.window.cursor = (index[0]+1, 0)
            vim.command('call s:fold_open()')
        else:
            print('Already Delete/Move/Change folder/tag')


def connect_thread_tree():
    r_msg_id = get_msg_id()
    if r_msg_id == '':
        return
    bufnr = vim.current.buffer
    search_term = bufnr.vars['search_term'].decode()
    bufnr = bufnr.number
    if bufnr != vim.bindeval('s:buf_num')['thread'] \
            and not (search_term in vim.bindeval('s:buf_num')['search']) \
            and bufnr != vim.bindeval('s:buf_num')['search'][search_term]:
        print_warring('The command can only be used on thread/search.')
        return
    lines = get_mark_in_thread()
    if lines == []:
        print_warring('Mark the email that you want To connect. (:Notmuch mark)')
        return
    DBASE.open(PATH)
    for line in lines:
        msg_id = THREAD_LISTS[search_term][line].get_message_id()
        if r_msg_id == msg_id:
            continue
        msg = DBASE.find_message(msg_id)
        for f in msg.get_filenames():
            with open(f, 'r') as fp:
                msg_file = email.message_from_file(fp)
            ref_all = ''
            refs = msg_file.get_all('References')
            if refs is None:
                ref_all = ''
            else:
                for ref in refs:
                    ref_all += ref
            if ref_all == '':
                msg_file.__setitem__('References', '<' + r_msg_id + '>')
            elif '<' + r_msg_id + '>' not in ref_all:
                msg_file.replace_header(
                    'References', ref_all + ' <' + r_msg_id + '>')
            if msg_file.get_all('In-Reply-To') is None:
                msg_file.__setitem__('In-Reply-To', '<' + r_msg_id + '>')
            else:
                msg_file.replace_header('In-Reply-To', '<' + r_msg_id + '>')
            with open(f, 'w') as fp:
                fp.write(msg_file.as_string())
            shellcmd_popen(['notmuch', 'reindex', 'id:' + msg_id])
    DBASE.close()
    print_thread(bufnr, search_term, False, True)
    index = [i for i, x in enumerate(
        THREAD_LISTS[search_term]) if x.get_message_id() == r_msg_id]
    if len(index):
        vim.current.window.cursor = (index[0]+1, 0)
        vim.command('call s:fold_open()')
    else:
        print('Already Delete/Move/Change folder/tag')


def get_mark_in_thread():  # マークの付いた先頭行を 0 とした行番号リストを返す
    lines = []
    # notmuch-thread と notmuch-search からしか呼ばれないので、bufnr() を調べない
    signs = vim.bindeval('sign_getplaced(' + str(vim.current.buffer.number) +
                         ', {"name":"notmuch", "group":"mark_thread"})')[0]['signs']
    for i in range(len(signs)):
        lines.append(signs[i]['lnum']-1)
    return lines


def get_save_dir():
    if 'notmuch_save_dir' in vim.vars:
        # 設定が有れば ~ や $HOME などの環境変数展開
        save_path = os.path.expandvars(
                re.sub('^~/', '$HOME/', vim.vars['notmuch_save_dir'].decode()))
        return os.path.expandvars(save_path).replace('/', os.sep)+os.sep
    else:
        return os.getcwd()+os.sep


def get_save_filename(path):  # 保存ファイル名の取得 (既存ファイルなら上書き確認)
    while True:
        path = vim.eval('input("Save as: ", "'+path+'", "file")')
        if path == '':
            return ''
        elif os.path.isfile(path):
            over_write = vim.eval('input("Overwrite '+path+'? [y/N]: ","")').lower()
            if over_write == 'yes' or over_write == 'y':
                return path
        elif os.path.isdir(path):
            print_warring('\'' + path + '\' is directory.')
        else:
            return path


def view_mail_info():  # メール情報表示
    def get_mail_info():
        vc = vim.current
        b = vc.buffer
        bnum = b.number
        if bnum == vim.bindeval('s:buf_num')['folders']:
            search_term = vim.vars['notmuch_folders'][vc.window.cursor[0]-1][1].decode()
            return [search_term]
        msg_id = get_msg_id()
        if msg_id == '':
            return
        search_term = b.vars['search_term'].decode()
        DBASE.open(PATH)
        msg = list(notmuch.Query(
            DBASE, '('+search_term+') id:'+msg_id).search_messages())
        if len(msg):
            msg = list(msg)[0]
        else:  # 同一条件+Message_ID で見つからなくなっているので Message_ID だけで検索
            print('Already Delete/Move/Change folder/tag')
            msg = DBASE.find_message(msg_id)
        if bnum == vim.bindeval('s:buf_num')['thread'] \
            or ((search_term in vim.bindeval('s:buf_num')['search'])
                and bnum == vim.bindeval('s:buf_num')['search'][search_term]):
            lists = ['search term: ' + search_term]
        else:
            lists = []
        lists += ['msg-id     : ' + msg_id, 'tags       : ' + get_msg_tags(msg)]
        for f in msg.get_filenames():
            if os.path.isfile(f):
                lists += ['file       : ' + f,
                          'Modified   : ' +
                          datetime.datetime.fromtimestamp(os.path.getmtime(f)).strftime(DATE_FORMAT),
                          'Size       : ' + str(os.path.getsize(f)) + ' Bytes']
            else:
                lists.append('file       : ' + f + '\n' + '             Already Delte.')
        DBASE.close()
        pgp_result = b.vars['pgp_result'].decode()
        if pgp_result != '':
            lists.append('PGP result : ' + pgp_result.split('\n')[1])
            for ls in pgp_result.split('\n')[2:]:
                if ls != '':
                    lists.append('             ' + ls)
        return lists

    info = get_mail_info()
    if vim.bindeval('has("popupwin")'):
        vim_ls = '["'
        for ls in info:
            vim_ls += ls.replace('\\', '\\\\').replace('"', '\\"') + '","'
        # info = '["' + '","'.join(info) + '"]'
        vim_ls = vim_ls[:-2] + ']'
        vim.command('call popup_atcursor(' + vim_ls +
                    ',{' +
                    '"border": [1,1,1,1],' +
                    '"drag": 1,' +
                    '"close": "click",' +
                    '"moved": "any",' +
                    '"filter": function("s:close_popup"),' +
                    '"mapping": 0' +
                    '})')
    else:
        print('\n'.join(info))


def open_original(msg_id, search_term, args):  # vim から呼び出しでメール・ファイルを開く
    def find_mail_file(search_term):  # 条件に一致するファイルを探す
        msgs = notmuch.Query(DBASE, search_term).search_messages()
        files = []
        for msg in msgs:
            for filename in msg.get_filenames():
                files.append(filename)
        if len(files) == 0:
            return ''
        else:
            return files[0]

    DBASE.open(PATH)
    message = ''
    filename = find_mail_file(
        '(' + search_term + ') id:'+msg_id)
    if filename == '':
        message = 'Already Delete/Move/Change folder/tag'
        filename = find_mail_file('id:'+msg_id)
    DBASE.close()
    if filename == '':
        message = 'Not found file.'
    else:
        # 開く前に呼び出し元となるバッファ変数保存
        b_v = vim.current.buffer.vars
        subject = b_v['subject']
        date = b_v['date']
        with open(filename, 'rb') as fp:
            msg_file = email.message_from_binary_file(fp)
        for part in msg_file.walk():  # 最初の Content-Type: text/xxxx を探す
            if part.is_multipart():
                continue
            if part.get_content_disposition() == 'attachment':  # 先に判定しないと、テキストや HTML ファイルが本文扱いになる
                if part.get_content_type().find('application/pgp-encrypted') == 0:
                    encoding = None
                    charset = 'us-ascii'
                    break
            else:
                content_type = part.get_content_type()
                # メールを単純にファイル保存した時は UTF-8 にしているので、それをインポートしたときのため
                charset = part.get_content_charset('utf-8')
                encoding = part.get('Content-Transfer-Encoding')
                if content_type.find('text/') == 0:
                    break
        # for charset in msg_file.get_charsets():
        #     if charset is not None:
        #         break  # 複数の文字コードであっても vim 自体がその様なファイルに対応していないだろうから、最初の文字コードで開く
        if encoding is not None:
            encoding = encoding.lower()
        active_win = str(vim.current.buffer.number)
        if encoding == 'quoted-printable' or encoding == 'base64':
            vim.command(vim.vars['notmuch_open_way']['edit'].decode()
                        + ' ' + filename)
            print_warring('The mail is ' + encoding + '.')
        else:
            vim.command(vim.vars['notmuch_open_way']['edit'].decode()
                        + ' ++encoding=' + charset + ' ' + filename)
        # 保存しておいたバッファ変数を開いたバッファに写す
        b_v = vim.current.buffer.vars
        b_v['subject'] = subject
        b_v['date'] = date
        vim.command('call s:augroup_notmuch_select(' + active_win + ', 1)')
        vim.command('call s:fold_mail_header() | set foldtext=FoldHeaderText()')
        vim.command('setlocal filetype=notmuch-edit')
    if message != '':
        vim.command('redraw')  # redraw しないと次のメッセージがすぐに消えてしまう
        print(message)


# def set_atime_now():  # ファイルのアクセス時間を現在時刻に
#     msg_id = get_msg_id()
#     if msg_id == '':
#         return
#     DBASE.open(PATH)
#     for filename in DBASE.find_message(msg_id).get_filenames():
#         stat_info = os.stat(filename)
#         m_time = int(stat_info.st_mtime)
#         os.utime(filename, (time.time(), m_time))


def send_mail(filename):  # ファイルをメールとして送信←ファイルは削除/送信済み保存
    with open(filename, 'r') as fp:
        msg_data = fp.read()
        # msg_file = email.message_from_file(fp) を用いるとヘッダがエンコードされる+不正なヘッダ書式をチェック出来ない
    if send_str(msg_data):
        os.remove(filename)


def send_vim_buffer():
    msg_data = '\n'.join(vim.current.buffer[:])
    if send_str(msg_data):
        if vim.bindeval('len(getbufinfo())') == 1:  # 送信用バッファのみ
            vim.command('cquit')
        vim.command('bwipeout!')


def send_str(msg_data):  # 文字列をメールとして保存し設定従い送信済みに保存
    def set_header(msg, header, data):  # エンコードしてヘッダ設定
        for charset in SENT_CHARSET:
            try:
                if charset == 'us-ascii' or charset == 'ascii':
                    data.encode(charset)
                    # ↑ASCII 指定で ASCII 以外が含まれると全て UTF-8 として扱うので本当に ASCII 変換可能か試す
                msg[header] = email.header.Header(data, charset)
                break
            except UnicodeEncodeError:
                pass
        else:
            msg[header] = email.header.Header(data, 'utf-8')

    def attach_file(msg, path):  # 添付ファイルを追加
        if path == '':
            return True
        path = os.path.expandvars(re.sub('^~/', '$HOME/', path))
        if not os.path.isfile(path):
            print_err('Not exit: ' + path)
            return False
        # 添付ファイルの各 part のヘッダ部に付けるファイル情報
        for charset in SENT_CHARSET:
            filename = os.path.basename(path)
            try:
                filename.encode(charset)  # 変換可能か試す
            except UnicodeEncodeError:
                continue
            if charset == 'us-ascii' or charset == 'ascii':
                name_param = {'name': filename}
                file_param = {'filename': filename}
            else:
                name_param = {'name': email.charset.Charset(
                    charset).header_encode(filename)}
                # 一方のファイル名はヘッダのエンコード表現と同じにしておく
                file_param = {'filename': (charset, '', filename)}
            break
        else:
            name_param = {'name': email.charset.Charset(
                'utf-8').header_encode(filename)}
            file_param = {'filename': ('utf-8', '', filename)}
        file_param.update({
            'size': str(os.path.getsize(path)),
            'creation-date': email.utils.formatdate(os.path.getctime(path), localtime=True),
            'modification-date': email.utils.formatdate(os.path.getmtime(path), localtime=True)})
        # 添付ファイルの実際のファイルデータ生成+とヘッダ部の追加
        mimetype, mimeencoding = mimetypes.guess_type(path)
        if mimetype is None or mimeencoding is not None:
            print_warring('Not found mimetyp.  Attach with \'application/octet-stream\'')
            mimetype = 'application/octet-stream'
        maintype, subtype = mimetype.split('/')
        if maintype == 'text':
            with open(path, 'r') as fp:
                part = MIMEText(fp.read(), _subtype=subtype)
        else:
            with open(path, 'rb') as fp:
                part = MIMEBase(maintype, subtype, **name_param)
                part.set_payload(fp.read())
                email.encoders.encode_base64(part)
        part.add_header('Content-Disposition', 'attachment', **file_param)
        msg.attach(part)
        return True

    def set_header_address(msg, header, address):  # ヘッダにエンコードした上でアドレスをセット
        pair = ''
        while len(address):
            match_str = re.match(' *"[^"]+"[^,]+', address)
            if match_str is None:
                match_str = re.match(' *[^,]+', address)
            if match_str is None:
                one_pair = address
            else:
                one_pair = re.sub(' *(.+) *', r'\1', match_str.group(0))
            address = address[match_str.end(0)+1:]
            one_pair = email.utils.parseaddr(one_pair)
            for charset in SENT_CHARSET:
                try:
                    one_pair = email.utils.formataddr(one_pair, charset)
                    break
                except UnicodeEncodeError:
                    pass
            else:
                one_pair = email.utils.formataddr(one_pair, 'utf-8')
            pair += ', ' + one_pair
        msg[header] = pair[2:]

    def get_user_id(From):  # get User ID and domain from mail adress setting
        mail_address = None
        if From is None:
            if VIM_MODULE:
                if 'notmuch_from' in vim.vars:
                    mail_address = vim.vars['notmuch_from'][0]['address'].decode()
        else:
            mail_address = From
        if mail_address is None:
            mail_address = get_config('user.primary_email')
        # if mail_address is None:  # ↑何某か標準の設定が返される
        #     return None, None
        mail_address = email2only_address(mail_address)
        index = mail_address.find('@')
        if index == -1:
            return None, None
        msgid_id = mail_address[:index]
        msgid_domain = mail_address[index+1:]
        return msgid_id, msgid_domain

    if shutil.which(SEND_PARAM[0]) is None:
        sys.stderr.write('\'' + SEND_PARAM[0] + '\' is not executable.')
        return False
    if 'utf-8' in SENT_CHARSET:  # utf-8+8bit を可能にする 無いとutf-8+base64
        email.charset.add_charset(
            'utf-8', email.charset.SHORTEST, None, 'utf-8')
    # ヘッダ・本文の分離と添付有無の分岐
    match = re.search(r'\n\n', msg_data)
    if match is None:
        headers = msg_data
        mail_context = ''
    else:
        headers = msg_data[:match.start()]
        # ファイル末尾の連続する改行は一旦全て削除
        mail_context = re.sub(r'\n+$', '', msg_data[match.end():])
        mail_context = re.sub(r'^\n+', '', mail_context) + '\n'  # 本文最初の改行は全て削除し、最後に改行追加
    flag_attach = re.search(r'^Attach:\s*[^\s]+', headers, re.MULTILINE + re.IGNORECASE) is None
    flag_encypt = re.search(r'^Encrypt:\s*[^\s]+', headers, re.MULTILINE + re.IGNORECASE) is None
    flag_sig = re.search(r'^Signature:\s*[^\s]+', headers, re.MULTILINE + re.IGNORECASE) is None
    if not (flag_attach or flag_encypt or flag_sig):
        attachments = None
        for charset in SENT_CHARSET:
            try:
                msg_send = MIMEText(mail_context.encode(charset), 'plain', charset)
                break
            except UnicodeEncodeError:
                pass
        else:
            msg_send = MIMEText(mail_context.encode('utf-8'), 'plain', 'utf-8')
    else:
        attachments = []
        msg_send = MIMEMultipart()
        for charset in SENT_CHARSET:
            try:
                msg_send.attach(MIMEText(mail_context.encode(charset), 'plain', charset))
                break
            except UnicodeEncodeError:
                pass
        else:
            msg_send.attach(
                MIMEText(mail_context.encode('utf-8'), 'plain', 'utf-8'))
    # ヘッダ文字列情報をリストに変換
    header_data = {}
    pre_header = ''
    for header in headers.split('\n'):
        match = re.match(r'^[A-Za-z-]+:\s*', header)
        if match is None:
            match = re.match(r'^\s+', header)
            if match is None:
                sys.stderr.write('Illegal header')
                return False
            header_data[pre_header] += header[match.end():]
        else:
            header_term = header[:header.find(':')]
            header_item = header[match.end():]
            if header_item != '':
                if header_term.lower() == 'attach':
                    attachments.append(header_item)
                else:
                    header_data[header_term] = header_item
            pre_header = header_term
    # 送信メールのヘッダ設定+添付ファイル追加
    msg_data = ''
    send_headers = ['from', 'to', 'cc', 'bcc', 'reply-to',
                    'resent-to', 'resent-cc', 'resent-bcc']
    ignore_msg_data = ['date', 'content-type', 'content-transfer-encoding']
    fcc = ''
    x_header = {}
    for header_term, h_data in header_data.items():
        header_lower = header_term.lower()
        if header_lower == 'fcc':
            fcc = h_data
        elif (header_lower in ignore_msg_data) or h_data == '':
            pass
        else:
            msg_data += '\n' + header_term + ': ' + h_data  # 送信済みとして下書きを使う場合に備えたデータ作成
            if header_lower in send_headers:
                set_header_address(msg_send, header_term, h_data)
            elif header_lower[:1] != 'x-':  # X-??? ヘッダは送信しない
                set_header(msg_send, header_term, h_data)
            else:
                x_header[header_term] = h_data  # 送信済みとしては保存したほうが良いだろう
    if attachments is not None:
        for attachment in attachments:
            if not attach_file(msg_send, attachment):
                return False
    #  必須ヘッダの追加
    if msg_send.get('Subject') is None:
        msg_send['Subject'] = ''
    if msg_send.get('To') is None and msg_send.get('Cc') is None:
        if msg_send.get('Bcc') is None:
            print_warring('No address')
            return False
        msg_send['To'] = 'undisclosed-recipients: ;'
    #  Message-ID が元ファイルになければ作成
    msg_id = msg_send.get('Message-ID')
    if msg_id is None:
        msgid_id, msgid_domain = get_user_id(msg_send.get('From'))
        if msgid_id is None:
            msg_id = email.utils.make_msgid()
        else:
            msg_id = email.utils.make_msgid(msgid_id.upper(), msgid_domain.upper())
        msg_send['Message-ID'] = msg_id
    else:
        msg_id = msg_id.__str__()
    del msg_send['Date']
    msg_date = email.utils.formatdate(localtime=True)
    msg_send['Date'] = msg_date
    # 送信
    try:
        pipe = Popen(SEND_PARAM, stdin=PIPE, stdout=PIPE, stderr=PIPE, encoding='utf8')
    except Exception as err:
        sys.stderr.write(err)
        return False
    pipe, err = pipe.communicate(msg_send.as_string())
    if err != '':
        sys.stderr.write(err)
        return False
    print(pipe)
    in_reply = msg_send.get('In-Reply-To')
    if in_reply is not None:  # 送信メールに In-Reply-To が有れば、送信元ファイルに replied タグ追加
        msg = change_tags_before(in_reply.__str__()[1:-1])
        add_msg_tags(msg, ['replied'])
        change_tags_after(msg, True)
    # 送信済みファイルの作成
    make_dir(TEMP_DIR)
    send_tmp = TEMP_DIR + 'send.tmp'
    with open(send_tmp, 'w') as fp:  # utf-8 だと、Mailbox に取り込めないので一度保存してバイナリで読込し直す
        save_draft_file = False
        if VIM_MODULE:
            if vim.vars['notmuch_save_draft'] == 1:
                save_draft_file = True
        if save_draft_file:
            msg_data = msg_data[1:]
            msg_data += '\nDate: ' + msg_date + \
                '\nContent-Type: text/plain; charset="utf-8"\nContent-Transfer-Encoding: 8bit'
            if re.search(r'^Message-ID:\s*', headers, re.MULTILINE) is None:
                msg_data += '\nMessage-ID: ' + msg_id
            if attachments is not None:
                for attachment in attachments:
                    msg_data += '\nX-Attach: ' + attachment
            msg_data += '\n\n' + mail_context
            fp.write(msg_data)
        else:
            for header_term, h_data in x_header.items():  # X-??? ヘッダを送信済みメールには残す
                set_header_address(msg_send, header_term, h_data)
            fp.write(msg_send.as_string())
    # 保存先メール・フォルダの設定
    if fcc != '' and os.path.isdir(PATH + os.sep + fcc):
        sent_dir = fcc
    elif VIM_MODULE:
        sent_dir = vim.vars['notmuch_save_sent_mailbox'].decode()
        if sent_dir == '':  # 空なら送信済みを保存しない
            return True
    else:
        sent_dir = 'sent'
    if attachments is None:
        add_tag = ['sent']
    else:
        add_tag = ['sent', 'attachment']
    DBASE.open(PATH)
    msg = DBASE.find_message(msg_id[1:-1])
    if msg is not None:
        add_tag.append(msg.get_tags())
        add_tag.remove('draft')
    DBASE.close()
    move_mail_main(msg_id[1:-1], send_tmp, sent_dir, ['draft'], add_tag)  # 送信済み保存
    return True


def new_mail(s):  # 新規メールの作成 s:mailto プロトコルを想定
    def get_mailto(s, headers):  # mailto プロトコルからパラメータ取得
        if len(s) == 0:
            headers['to'] = ''
            return
        s = s[0]
        if s[:7] == 'mailto:':
            s = s[7:]
        re_match = re.search(r'\?[A-Za-z-]+=', s)
        if re_match is None:
            headers['to'] = s
            return
        headers['to'] = s[:re_match.start()]
        s = s[re_match.start():]
        while True:
            header_len = re_match.end()-re_match.start()
            header = s[1:header_len-1].lower()
            s = s[header_len:]
            re_match = re.search(r'\?[A-Za-z-]+=', s)
            if re_match is None:
                headers[header] = unquote(s)
                return
            else:
                headers[header] = unquote(s[:re_match.start()])
                s = s[re_match.start():]

    def get_user_To(b):  # notmuch_folders のカーソル位置や search_term から宛先取得
        def get_user_To_folder():
            s = vim.vars['notmuch_folders'][vim.current.window.cursor[0]-1][1].decode()
            to = ''
            for i in vim.vars.get('notmuch_to', []):
                d = i[0].decode()
                if d == '*':
                    to = i[1].decode()
                elif re.search(r'\b' + re.escape(d) + r'\b', s) is not None:
                    return i[1].decode()
            return to

        bufnr = str(b.number)
        msg_id = get_msg_id()
        to = ''
        if msg_id != '':
            DBASE.open(PATH)
            for i in vim.vars.get('notmuch_to', []):
                s = i[0].decode()
                if notmuch.Query(DBASE, '(' + s + ') and id:' + msg_id).count_messages():
                    return i[1].decode()
            DBASE.close()
        elif is_same_tabpage('folders', ''):
            vim.command('call win_gotoid(bufwinid(s:buf_num["folders"]))')
            to = get_user_To_folder()
            vim.command('call win_gotoid(bufwinid(' + bufnr + '))')
        return to

    headers = {'subject': ''}
    get_mailto(s, headers)
    b = vim.current.buffer
    if headers['to'] == '':
        headers['to'] = get_user_To(b)
    active_win = str(b.number)
    before_make_draft(active_win)
    b = vim.current.buffer
    b.vars['subject'] = headers['subject']
    for header in vim.vars['notmuch_draft_header']:
        header = header.decode()
        header_l = header.lower()
        if header_l in headers:
            b.append(header + ': ' + headers.pop(header_l))
        else:
            b.append(header + ': ')
    for header in headers:
        b.append(header + ': ' + headers[header])
    b.append('')
    after_make_draft(b)
    vim.command('call s:au_new_mail()')


def reply_mail():  # 返信メールの作成
    def delete_duplicate_addr(x_ls, y_ls):  # x_ls から y_ls と重複するアドレス削除
        # 重複が合ったか? 最初に見つかった重複アドレスを返す
        # y_ls は実名の削除されたアドレスだけが前提
        exist = False
        dup = ''
        for x in x_ls:
            if 'undisclosed recipients:;' == x.lower():
                x_ls.remove(x)
        for x in x_ls:
            if email2only_address(x) in y_ls:
                if not exist:
                    dup = x.strip()
                exist = True
                x_ls.remove(x)
        return exist, dup

    def address2ls(adr):  # To, Cc ヘッダのアドレス群をリストに
        if adr == '':
            return []
        adr_ls = []
        # ヘッダの「名前+アドレス」は " に挟まれた部分と、コメントの () で挟まれた部分以外では、, が複数個の区切りとなる
        # また " で挟まれた部分も、() で挟まれた部分も \ がエスケープ・キャラクタ
        for x in re.finditer(r'("(\\"|[^"])*"|\((\\\(|\\\)|[^()])*\)|[^,])+', adr):
            adr_ls.append(re.sub(r'\s*(.+)\s*', r'\1', x.group()))
        return adr_ls
        # 以下以前のバージョン
        # adr = adr.split(',')
        # for i, x in enumerate(adr):
        #     if x.count('"') == 1 and x.count('@') == 0 and adr[i+1].count('"') == 1:
        #         adr[i] = x+','+adr[i+1]
        #         del adr[i+1]
        # return adr

    active_win, msg_id = check_org_mail()
    if not active_win:
        return
    msg_data = get_mail_body(active_win)
    before_make_draft(active_win)
    b = vim.current.buffer
    b.vars['org_mail_body'] = msg_data
    DBASE.open(PATH)
    msg = DBASE.find_message(msg_id)
    headers = vim.vars['notmuch_draft_header']
    recive_from_name = msg.get_header('From')
    b.vars['org_mail_from'] = email2only_name(recive_from_name)
    recive_to_name = msg.get_header('To')
    from_ls = [email2only_address(get_config('user.primary_email'))]
    for i in vim.vars.get('notmuch_from', []):
        from_ls.append(email2only_address(i['address'].decode()))
    send_from_name = ''
    if email2only_address(recive_from_name) in from_ls:  # 自分のメールに対する返信
        send_to_name = recive_to_name
        send_from_name = recive_from_name
        cc_name = []
    else:
        recive_to_name = address2ls(recive_to_name)
        cc_name = address2ls(msg.get_header('Cc'))
        addr_exist = False
        addr_exist, send_from_name = delete_duplicate_addr(recive_to_name, from_ls)
        addr_tmp, send_tmp = delete_duplicate_addr(cc_name, from_ls)
        if not addr_exist:
            addr_exist = addr_tmp
            send_from_name = send_tmp
        send_to_name = ', '.join((recive_to_name+[recive_from_name]))
    for header in headers:
        header = header.decode()
        header_lower = header.lower()
        if header_lower == 'from':
            b.append('From: ' + send_from_name)
        elif header_lower == 'subject':
            subject = 'Re: ' + msg.get_header('Subject')
            b.append('Subject: ' + subject)
            b.vars['subject'] = subject
        elif header_lower == 'to':
            to = msg.get_header('Reply-To')
            if to == '':
                to = send_to_name
            b.append('To: ' + to)
        elif header_lower == 'cc':
            b.append('Cc: ' + ', '.join(cc_name))
        elif header_lower == 'attach':  # これだけは必ず最後
            pass
        else:
            b.append(header + ': ')
    set_reference(b, msg, True)
    if next((i for i in headers if i.decode().lower() == 'attach'), None) is not None:
        b.append('Attach: ')
    b.vars['org_mail_date'] = email.utils.parsedate_to_datetime(
        msg.get_header('Date')).strftime('%Y-%m-%d %H:%M %z')
    # date = email.utils.parsedate_to_datetime(msg.get_header('Date')).strftime(DATE_FORMAT)
    # ↑同じローカル時間同士でやり取りするとは限らない
    DBASE.close()
    after_make_draft(b)
    vim.command('call s:au_reply_mail()')


def forward_mail():
    windo, msg_id = check_org_mail()
    if not windo:
        return
    msg_data = get_mail_body(windo)  # 実際には後からヘッダ情報なども追加
    DBASE.open(PATH)
    msg = DBASE.find_message(msg_id)
    msg_data = '\n' + msg_data
    before_make_draft(windo)
    b = vim.current.buffer
    cut_line = 70
    for h in ['Cc', 'To', 'Date', 'Subject', 'From']:
        s = msg.get_header(h).replace('\t', ' ')
        if s != '':
            msg_data = h + ': ' + ' ' * (7-len(h)) + s + '\n' + msg_data
        if h == 'Subject':
            subject = 'FWD:' + s
            b.vars['subject'] = subject
        s_len = 9 + vim.bindeval('strdisplaywidth("' + s.replace('"', '\\"') + '")')
        cut_line = max(cut_line, s_len)
    headers = vim.vars['notmuch_draft_header']
    for h in headers:
        h = h.decode()
        h_lower = h.lower()
        if h_lower == 'subject':
            b.append('Subject: ' + subject)
        elif h_lower == 'attach':  # これだけは必ず最後
            pass
        else:
            b.append(h + ': ')
    set_reference(b, msg, False)
    if next((i for i in headers if i.decode().lower() == 'attach'), None) is not None:
        b.append('Attach: ')
    DBASE.close()
    # 本文との境界線作成
    message = 'Forwarded message'
    mark = '-' * int((cut_line - vim.bindeval('strdisplaywidth("' +
                      message.replace('"', '\\"') + '")') - 2) / 2)
    msg_data = mark + ' ' + message + ' ' + mark + '\n' + msg_data
    # 本文との境界線作成終了
    b.vars['org_mail_body'] = msg_data
    b.append('')
    after_make_draft(b)
    vim.command('call s:au_forward_mail()')


def before_make_draft(active_win):  # 下書き作成の前処理
    if vim.current.buffer.options['filetype'].decode()[:8] == 'notmuch-' \
            or vim.bindeval('wordcount()["bytes"]') != 0:
        vim.command(vim.vars['notmuch_open_way']['draft'].decode())
    vim.command('call s:mail_quote()')
    vim.command('setlocal filetype=notmuch-draft buftype=nofile')
    vim.command('call s:augroup_notmuch_select(' + active_win + ', 0)')


def after_make_draft(b):
    b.append('')
    del b[0]
    b.options['modified'] = 0


def set_new_after(n):  # 新規メールの From ヘッダの設定や署名の挿入
    if vim.current.window.cursor[0] < vim.bindeval('line("$")'):
        return
    vim.command('autocmd! NotmuchNewAfter' + str(n))
    to, h_from = set_from()
    insert_signature(to, h_from)


def check_org_mail():  # 返信・転送可能か? 今の bufnr() と msg_id を返す
    b = vim.current.buffer
    is_search = b.number
    b.vars['subject'] = ''
    active_win = str(is_search)
    show_win = vim.bindeval('s:buf_num')['show']
    is_search = not(vim.bindeval('s:buf_num')['folders'] == is_search
                    or vim.bindeval('s:buf_num')['thread'] == is_search
                    or show_win == is_search)
    if is_search:
        show_win = vim.bindeval('s:buf_num')["view"][vim.current.buffer.vars['search_term'].decode()]
    if vim.bindeval('win_gotoid(bufwinid(' + str(show_win) + '))') == 0:
        return 0, ''
    msg_id = get_msg_id()
    if msg_id == '':
        vim.command('call win_gotoid(bufwinid(' + active_win + '))')
        return 0, ''
    return active_win, msg_id


def get_mail_body(active_win):
    msg_data = '\n'.join(vim.current.buffer[:])
    match = re.search(r'\n\n', msg_data)
    if match is None:
        vim.command('call win_gotoid(bufwinid(' + active_win + '))')
        return ''
    msg_data = re.sub(r'\n+$', '', msg_data[match.end():])
    match = re.search(r'\n\fHTML part\f\n', msg_data)
    if match is not None:  # HTML メール・パート削除
        msg_data = msg_data[:match.start()]
    vim.command('call win_gotoid(bufwinid(' + active_win + '))')
    return re.sub(r'^\n+', '', msg_data)


def set_reference(b, msg, flag):  # References, In-Reply-To, Fcc 追加
    # In-Reply-To は flagg == True
    re_msg_id = ' <' + msg.get_header('Message-ID') + '>'
    b.append('References: ' + msg.get_header('References') + re_msg_id)
    if flag:
        b.append('In-Reply-To:' + re_msg_id)
    fcc = msg.get_filenames().__str__().split('\n')[0]
    fcc = fcc[len(PATH)+1:]
    if MAILBOX_TYPE == 'Maildir':
        fcc = re.sub(r'/(new|tmp|cur)/[^/]+', '', fcc)
    else:
        fcc = re.sub('/[^/]+$', '', fcc)
    b.append('Fcc:' + fcc)


def set_reply_after(n):  # 返信メールの From ヘッダの設定や引用本文・署名の挿入
    if vim.current.window.cursor[0] < vim.bindeval('line("$")'):
        return
    vim.command('autocmd! NotmuchReplyAfter' + str(n))
    to, h_from = set_from()
    b = vim.current.buffer
    if vim.vars.get('notmuch_signature_prev_quote', 0):
        insert_signature(to, h_from)
    b.append('On ' + b.vars['org_mail_date'].decode() + ', ' +
             email2only_name(b.vars['org_mail_from'].decode()) + ' wrote:')
    for line in b.vars['org_mail_body'].decode().split('\n'):
        b.append('> ' + line)
    b.append('')
    if not vim.vars.get('notmuch_signature_prev_quote', 0):
        insert_signature(to, h_from)
    del b.vars['org_mail_date']
    del b.vars['org_mail_body']
    del b.vars['org_mail_from']


def set_forward_after(n):  # 返信メールの From ヘッダの設定や引用本文・署名の挿入
    if vim.current.window.cursor[0] < vim.bindeval('line("$")'):
        return
    vim.command('autocmd! NotmuchForwardAfter' + str(n))
    to, h_from = set_from()
    b = vim.current.buffer
    if vim.vars.get('notmuch_signature_prev_forward', 0):
        insert_signature(to, h_from)
    for line in b.vars['org_mail_body'].decode().split('\n'):
        b.append(line)
    b.append('')
    if not vim.vars.get('notmuch_signature_prev_forward', 0):
        insert_signature(to, h_from)
    del b.vars['org_mail_body']


def set_from():  # 宛先に沿って From ヘッダを設定と b:subject の書き換え
    def get_user_From(to):  # get From setting
        default_addr = get_config('user.primary_email')
        mail_address = vim.vars.get('notmuch_from', [])
        if len(mail_address) == 1:
            return mail_address[0]['address'].decode()
        elif len(mail_address) > 1:
            addr = ''
            for j in mail_address:
                l_to = j.get('To', b'').decode()
                if l_to == '':
                    continue
                elif l_to == '*':
                    addr = j['address'].decode()
                else:
                    for t in to:
                        if re.search(l_to, t) is not None:
                            return j['address'].decode()
            if addr != '':
                return addr
            lst = ''
            for i, j in enumerate(mail_address):
                lst += str(i+1) + '. ' + \
                    j['id'].decode() + ': ' + \
                    j['address'].decode() + '\n'
            while True:
                s = vim.eval('input("Select using From:.  When only [Enter], use default (' +
                             default_addr + ').\n' + lst + '")')
                if s == '':
                    return default_addr
                try:
                    s = int(s)
                except ValueError:
                    vim.command('echo "\n" | redraw')
                    continue
                if s >= 1 and s <= i:
                    break
                else:
                    vim.command('echo "\n" | redraw')
                    continue
            return mail_address[s-1]['address'].decode()
        return default_addr

    to = []
    h_from = (0, '')
    for i, b in enumerate(vim.current.buffer):
        match = re.match(r'(From|To|Cc|Bcc|Subject): *(.*)', b, flags=re.IGNORECASE)
        if match is None:
            continue
        elif match.group(1).lower() == 'subject':
            vim.current.buffer.vars['subject'] = match.group(2)
        elif match.group(1).lower() == 'from':
            h_from = (i, match.group(2))
        else:
            g = match.group(2)
            if g != '':
                to.append(g)
    if h_from[1] == '':
        h_From = get_user_From(to)
        vim.current.buffer[h_from[0]] = 'From: ' + h_From
    else:
        h_From = h_from[1]
    to = sorted(set(to), key=to.index)
    return to, h_From


def insert_signature(to_name, from_name):  # 署名挿入
    def get_signature(from_to):  # get signature filename
        if from_to == '':
            return ''
        if 'notmuch_signature' in vim.vars:
            sigs = vim.vars['notmuch_signature']
            from_to = email2only_address(from_to)
            sig = sigs.get(from_to, sigs.get('*', b'$HOME/.signature'))
            sig = os.path.expandvars(re.sub(r'^~/', '$HOME/', sig.decode()))
            if os.path.isfile(sig):
                return sig
        sig = os.path.expandvars('$HOME/.signature')
        if os.path.isfile(sig):
            return sig
        return ''

    sig = ''
    for t in to_name:
        sig = get_signature(to_name)
        if sig != '':
            break
    if sig == '':
        sig = get_signature(from_name)
    if sig != '':
        if os.path.getsize(sig) == 0:  # 空のファイルでも無駄に改行が入ってしまう
            return ''
        with open(sig, 'r') as fp:
            sig = fp.read()
    b = vim.current.buffer
    from_name = email2only_address(from_name)
    for line in sig.split('\n'):
        b.append(line.replace('@\t@', from_name))


def get_config(config):  # get notmuch setting
    ret = run(['notmuch', 'config', 'get', config], stdout=PIPE, stderr=PIPE)
    # if ret.returncode:  # 何某か標準の設定が返される
    #     print_err(ret.stderr.decode('utf-8'))
    #     return ''
    return ret.stdout.decode('utf-8').replace('\n', '')


def move_mail(msg_id, s, args):  # move mail to other mbox
    mbox = args[2:]
    if opened_mail():
        print_warring('Please save and close mail.')
        return
    if mbox == []:
        if MAILBOX_TYPE == 'Maildir':  # 入力初期値に先頭「.」付加
            mbox = "input('Move Mail folder: ', '.', 'customlist,Complete_Folder')"
        else:
            mbox = "input('Move Mail folder: ', '', 'customlist,Complete_Folder')"
        mbox = vim.eval(mbox)
        mbox = mbox.split()
    if mbox == [] or mbox is None:
        return
    mbox = mbox[0]
    if mbox == '' or mbox == '.':
        return
    DBASE.open(PATH)  # 呼び出し元で開く処理で書いてみたが、それだと複数メールの処理で落ちる
    msg = DBASE.find_message(msg_id)
    tags = msg.get_tags()
    for f in msg.get_filenames():
        if os.path.isfile(f):
            move_mail_main(msg_id, f, mbox, [], tags)
        else:
            print('Already Delte: ' + f)
    DBASE.close()
    if 'folders' in vim.bindeval('s:buf_num'):
        # 閉じた後でないと、メール・ファイル移動の情報がデータベースに更新されていないので、エラーになる
        DBASE.open(PATH)
        reprint_folder()
        DBASE.close()
    return [1, 1, mbox]  # Notmuch mark-command (command_marked) から呼び出された時の為、リストで返す


def move_mail_main(msg_id, path, move_mbox, delete_tag, add_tag):  # メール移動
    if opened_mail():
        print_warring('Please save and close mail.')
        return
    if MAILBOX_TYPE == 'Maildir':
        if move_mbox[0] == '.':
            move_mbox = PATH + os.sep + move_mbox
        else:
            move_mbox = PATH + os.sep + '.' + move_mbox
        if os.path.dirname(os.path.dirname(path)) == move_mbox:  # 移動先同じ
            return
        save_path = move_mbox + os.sep + 'new'
        mbox = mailbox.Maildir(move_mbox)
    elif MAILBOX_TYPE == 'MH':
        save_path = PATH + os.sep + move_mbox
        if os.path.dirname(os.path.dirname(path)) == save_path:  # 移動先同じ
            return
        mbox = mailbox.MH(save_path)
    else:
        print_err('Not support Mailbox type: ' + MAILBOX_TYPE)
        return False
    mbox.lock()
    msg_data = MIMEText('')
    save_path += os.sep + str(mbox.add(msg_data))  # MH では返り値が int
    shutil.move(path, save_path)
    mbox.flush()
    mbox.unlock()
    # タグの付け直し
    notmuch_new(False)
    msg = change_tags_before(msg_id)
    delete_tag += ['unread']  # mbox.add() は必ず unread になる
    delete_msg_tags(msg, delete_tag)
    add_msg_tags(msg, add_tag)  # 元々未読かもしれないので、追加を後に
    change_tags_after(msg, False)
    notmuch_new(False)
    if VIM_MODULE:
        # print_folder()
        vim.command('redraw')


def import_mail():
    if opened_mail():
        print_warring('Please save and close mail.')
        return
    # import path setting
    if VIM_MODULE:
        import_dir = vim.vars.get('notmuch_import_mailbox', b'').decode()
    if import_dir == '':
        import_dir = PATH
    elif MAILBOX_TYPE == 'Maildir':
        if import_dir[0] == '.':
            import_dir = PATH + os.sep + import_dir
        else:
            import_dir = PATH + os.sep + '.' + import_dir
    elif MAILBOX_TYPE == 'MH':
        import_dir = PATH + os.sep + import_dir
    else:
        print_err('Not support Mailbox type: ' + MAILBOX_TYPE)
        return
    make_dir(import_dir)
    if MAILBOX_TYPE == 'Maildir':
        mbox = mailbox.Maildir(import_dir)
        make_dir(import_dir + os.sep + 'new')
        make_dir(import_dir + os.sep + 'cur')
        make_dir(import_dir + os.sep + 'tmp')
    elif MAILBOX_TYPE == 'MH':
        mbox = mailbox.MH(import_dir)
    mbox.lock()
    f = vim.eval(
        'input("Import: ", "'+os.path.expandvars('$HOME/')+'", "file")')
    if f == '':
        return
    if os.path.isdir(f):  # ディレクトリならサブ・ディレクトリまで含めてすべてのファイルを対象とする
        if f[-1] == '/':
            f = glob.glob(f+'**', recursive=True)
        else:
            f = glob.glob(f+'/**', recursive=True)
        files = []
        for i in f:
            if not os.path.isdir(i):
                files.append(i)
    else:
        files = []
        files.append(f)
    msg_ids = []
    for f in files:
        try:
            with open(f, 'rb') as fp:
                msg = email.message_from_binary_file(fp)
        except FileNotFoundError:
            print_warring('No such file: ' + f)
            continue
        del msg['Delivered-To']
        msg_id = msg.get('Message-Id')
        if msg_id is None:
            print_warring('Import fail : '+f)
            continue
        if msg_id[0] == '<' and msg_id[-1] == '>':
            msg_id = msg_id[1:-1]
        msg_ids.append(msg_id)
        mbox.add(msg)
    mbox.flush()
    mbox.unlock()
    # タグの付け直し
    notmuch_new(False)
    # DBASE.open(PATH, mode=notmuch.Database.MODE.READ_WRITE)
    # for msg_id in msg_ids:
    #     msg = change_tags_before_core(msg_id)
    #     add_msg_tags(msg, ['inbox'])
    #     change_tags_after_core(msg, True)
    # DBASE.close()
    if VIM_MODULE:
        print_folder()
        vim.command('redraw')


def select_file(msg_id, question):  # get mail file list
    if msg_id == '':
        msg_id = get_msg_id()
        if msg_id == '':
            return [], ''
    DBASE.open(PATH)
    msg = DBASE.find_message(msg_id)
    subject = msg.get_header('Subject')
    prefix = len(PATH)+1
    files = []
    lst = ''
    size = 0
    len_i = 1
    for i, f in enumerate(msg.get_filenames()):
        if os.path.isfile(f):
            len_i += 1
            f_size = os.path.getsize(f)
            if size < f_size:
                size = f_size
    size = len(str(size))
    len_i = len(str(len_i))
    for i, f in enumerate(msg.get_filenames()):
        if os.path.isfile(f):
            fmt = '{0:<' + str(len_i) + '}|{1}| {2:>' + str(size) + '} B| {3}\n'
            lst += fmt.format(
                    str(i+1),
                    datetime.datetime.fromtimestamp(os.path.getmtime(f)).strftime(DATE_FORMAT),
                    str(os.path.getsize(f)),
                    f[prefix:])
            files.append(f)
        else:
            print_warring('Already Delete. ' + f[prefix:])
    DBASE.close()
    if len(files) == 1:
        return [files[0]], subject, 1
    i = i+1
    while True:
        s = vim.eval('input("' + question +
                     ' [1-' + str(i) + ']/[A]ll/[Enter]:[C]ancel\n' + lst + '")')
        if s == '' or s == 'C' or s == 'c':
            return [], '', 0
        elif s == 'A' or s == 'a':
            s = 'A'
            break
        else:
            try:
                s = int(s)
            except ValueError:
                vim.command('echo "\n" | redraw')
                continue
            if s >= 1 and s <= i:
                break
            else:
                vim.command('echo "\n" | redraw')
                continue
    if s == 'A':
        return files, subject, len(files)
    else:
        return [files[s-1]], subject, len(files)


def do_mail(cmd, args):  # mail に対しての処理、folders では警告表示
    # 行番号などのコマンド引数
    b = vim.current.buffer
    bnum = b.number
    try:
        search_term = b.vars['search_term'].decode()
    except KeyError:
        print_warring('Don\'t open mail or is done with \'folders\'.')
        return
    if search_term == '':
        print_warring('Don\'t open mail or is done with \'folders\'.')
        return
    if bnum == vim.bindeval('s:buf_num')['thread'] \
        or ((search_term in vim.bindeval('s:buf_num')['search'])
            and bnum == vim.bindeval('s:buf_num')['search'][search_term] + '\']'):
        args[0] = int(args[0])
        args[1] = int(args[1])
        for i in range(args[0], args[1]+1):
            msg_id = THREAD_LISTS[search_term][i-1].get_message_id()
            args = cmd(msg_id, search_term, args)
    elif (('show' in vim.bindeval('s:buf_num'))
            and bnum == vim.bindeval('s:buf_num')['show']) \
        or ((search_term in vim.bindeval('s:buf_num')['view'])
            and bnum == vim.bindeval('s:buf_num')['view'][search_term] + '\']'):
        args = cmd(b.vars['msg_id'].decode(), search_term, args)


def delete_mail(msg_id, s, args):  # s, args はダミー
    files, tmp, num = select_file(msg_id, 'Select delete file')
    if num == 1:
        while True:
            s = vim.eval('input("Delete ' + files[0] + '? [Y]es/[N]o? ", "Y")')
            if s == '' or s == 'N' or s == 'n':
                return
            elif s == 'Y' or s == 'y':
                break
    for f in files:
        os.remove(f)
    if not notmuch_new(True):
        print_warring('Can\'t update database.')


def export_mail(msg_id, s, args):  # s, args はダミー
    files, subject, tmp = select_file(msg_id, 'Select export file')
    s_dir = get_save_dir()
    subject = s_dir + re.sub(r'[\\/:\*\? "<>\|]', '-',
                             RE_TOP_SPACE.sub('', RE_END_SPACE.sub('', subject)))
    for i, f in enumerate(files):
        if i:
            path = subject + '(' + str(i) + ').eml'
        else:
            path = subject + '.eml'
        path = get_save_filename(path)
        if path != '':
            shutil.copyfile(f, path)


def get_mail_subfolders(root, folder, lst):  # get sub-mailbox lists
    path_len = len(PATH) + 1
    if MAILBOX_TYPE == 'Maildir':
        folder = root + os.sep + '.' + folder
        mbox = mailbox.Maildir(folder)
    elif MAILBOX_TYPE == 'MH':
        folder = root + os.sep + folder
        mbox = mailbox.MH(folder)
    else:
        # print_err('Not support Mailbox type: ' + MAILBOX_TYPE)
        return []
    lst.append(folder[path_len:])
    for f in mbox.list_folders():
        get_mail_subfolders(folder, f, lst)


def get_mail_folders():  # get mailbox lists
    if MAILBOX_TYPE == 'Maildir':
        mbox = mailbox.Maildir(PATH)
        notmuch_cnf_dir = 'notmuch'
    elif MAILBOX_TYPE == 'MH':
        mbox = mailbox.MH(PATH)
        notmuch_cnf_dir = '.notmuch'
    else:
        # print_err('Not support Mailbox type: ' + MAILBOX_TYPE)
        return []
    lst = []
    for folder in mbox.list_folders():
        if folder != notmuch_cnf_dir:
            get_mail_subfolders(PATH, folder, lst)
    lst.sort()
    return lst


def run_shell_program(msg_id, s, args):
    prg_param = args[2:]
    if len(prg_param) == 0:
        prg_param = vim.eval('input("Program and options: ", "", "shellcmd")')
        if prg_param == '':
            return
        else:
            prg_param = re.sub(
                ' +$', '', re.sub('^ +', '', prg_param)).split(' ')
    DBASE.open(PATH)
    msg = DBASE.find_message(msg_id)
    try:
        i = prg_param.index('<path:>')
        prg_param[i] = msg.get_filename()
    except ValueError:
        prg_param.append(msg.get_filename())
    DBASE.close()
    if '<id:>' in prg_param:
        i = prg_param.index('<id:>')
        prg_param[i] = msg_id
    shellcmd_popen(prg_param)
    print(' '.join(prg_param))
    return args


def get_command():  # マークしたメールを纏めて処理できるコマンド・リスト (command: must argument)
    # 実行不可能コマンド
    cannot_cmds = [
        'start',
        'open',
        'mail-info',
        'view-unread-page',
        'view-unread-mail',
        'view-previous',
        'close',
        'reload',
        'mail-new',
        'mail-reply',
        'mail-send',
        'mail-import',
        'mark',
        'thread-connect',
        'search',
        'thread-cut',
        'thread-connect',
        'search-thread',
    ]
    # 将来実行可能にするかもしれないコマンド
    cannot_cmds += [
        'mail-save',
        'mail-forward',
        'mail-reply'
    ]
    cmd_dic = {}
    cmds = vim.vars['notmuch_command']
    for cmd, v in cmds.items():
        cmd = cmd.decode()
        if cmd not in cannot_cmds:
            cmd_dic[cmd] = v[1]
    return cmd_dic


def get_cmd_name():  # コマンド名リスト
    return sorted([b.decode() for b in vim.vars['notmuch_command'].keys()], key=str.lower)


def get_mark_cmd_name():  # マークしたメールを纏めて処理できるコマンド名リスト
    return sorted(list(get_command().keys()), key=str.lower)


def get_last_cmd(cmds, cmdline, pos):  # コマンド列から最後のコマンドと引数が有るか? を返す
    regex = ' (' + '|'.join(cmds) + ') '
    result = list(re.finditer(regex, cmdline[:pos], flags=re.MULTILINE))
    if result == []:
        return []
    result = result[-1]
    last_str = cmdline[result.span()[1]:]
    # last_str = re.sub(r'^\s+', '', last_str)
    last_str = re.sub(r'^\s+', '', re.sub(r'\s+', ' ', last_str, flags=re.MULTILINE))
    return [result.group(1), ' ' in last_str]
    # 最後のコマンドより後ろで、それに続く空白を削除してなおどこかに空白が有れば引数を指定済み


def command_marked(cmdline):
    b = vim.current.buffer
    try:
        search_term = b.vars['search_term'].decode()
    except KeyError:
        print_warring('Don\'t open mail or is done with \'folders\'.')
        return
    if b.number != vim.bindeval('s:buf_num')['thread'] \
            and not (search_term in vim.bindeval('s:buf_num')['search']) \
            and b.number != vim.bindeval('s:buf_num')['search'][search_term]:
        print_warring('The command can only be used on thread/search.')
        return
    if b[0] == '':
        return
    marked_line = get_mark_in_thread()
    if marked_line == []:
        print_warring('Mark the email that you want to command. (:Notmuch mark)')
        return
    if cmdline == []:  # コマンド空
        cmdline = vim.eval(
            "input('Command: ', '', 'customlist,Complete_command')")
        if cmdline == '':
            return
        cmdline = cmdline.split()
    # コマンドの区切りである改行の前後に空白がない場合に対処
    arg_ls = []
    for cmd in cmdline:
        match = re.search(r'[\r\n\f]+', cmd)
        while match is not None:
            pre = cmd[:match.span()[0]]
            if pre != '':
                arg_ls.append(pre)
            arg_ls.append('\r')
            cmd = cmd[match.span()[1]:]
            match = re.search(r'[\r\n\f]+', cmd)
        if cmd != '':
            arg_ls.append(cmd)
    # 関数と引数のリスト作成
    cmds = get_command()
    cmds_dic = vim.vars['notmuch_command']
    cmd_arg = []
    cmd = ''
    args = []
    for arg in arg_ls:
        if cmd == '' and cmds[arg] == 1:  # 引数必要
            cmd = arg
        elif cmd == '' and cmds[arg] == 0:  # 引数を必要としないコマンド
            cmd_arg.append([cmds_dic[arg][0].decode()[2:], ''])
            cmd = ''
        elif arg == '\r' or arg == '\x00':  # コマンド区切り
            if cmd != '':
                cmd_arg.append([cmds_dic[cmd][0].decode()[2:], args])
                cmd = ''
                args = []
        else:  # コマンド引数
            args.append(arg)
    if cmd != '':
        cmd_arg.append([cmds_dic[cmd][0].decode()[2:], args])
    # 実際にここのメールにコマンド実行
    for i, cmd in enumerate(cmd_arg):
        for line in marked_line:
            msg_id = THREAD_LISTS[search_term][line].get_message_id()
            if cmd[0] in [  # 複数選択対応で do_mail() から呼び出されるものは search_term が必要
                          # 不要な場合はダミーの文字列
                          'add_tags',
                          'delete_mail',
                          'delete_tags',
                          'export_mail',
                          'move_mail',
                          'open_original',
                          'reindex_mail',
                          'run_shell_program',
                          'toggle_tags',
                          ]:
                args = GLOBALS[cmd[0]](msg_id, search_term, cmd[1])
            else:
                args = GLOBALS[cmd[0]](msg_id, cmd[1])
            cmd_arg[i][1] = args  # 引数が空の場合があるので実行した引数で置き換え
    vim.command(
        "call sign_unplace('mark_thread', {'name': 'notmuch', 'buffer': '', })")
    DBASE.open(PATH)
    if 'folders' in vim.bindeval('s:buf_num'):
        reprint_folder()
    DBASE.close()


def notmuch_search(search_term):
    search_term = search_term[2:]
    if search_term == '' or search_term == []:  # コマンド空
        if vim.current.buffer.number == vim.bindeval('s:buf_num')['folders']:
            search_term = vim.vars['notmuch_folders'][vim.current.window.cursor[0]-1][1]
            search_term = search_term.decode()
        else:
            search_term = vim.current.buffer.vars['search_term'].decode()
        search_term = vim.eval(
            'input("search term: ", "' + search_term + '", "customlist,Complete_search_input")')
        if search_term == '':
            return
    elif type(search_term) == list:
        search_term = ' '.join(search_term)
    DBASE.open(PATH)
    try:
        if notmuch.Query(DBASE, search_term).count_messages() == 0:
            DBASE.close()
            print_warring('Don\'t find mail.  (0 search mail).')
            return
    except notmuch.errors.XapianError:
        DBASE.close()
        vim.command('redraw')
        print_error('notmuch.errors.XapianError: Check search term: ' + search_term + '.')
        return
    DBASE.close()
    vim.command('call s:make_search_list(\'' + vim_escape(search_term) + '\')')
    b_num = vim.bindeval('s:buf_num')['search'][search_term]
    # if vim.bindeval('win_gotoid(bufwinid(' + str(b_num) + '))') \
    #         and vim.current.buffer.vars['search_term'].decode() == search_term:
    #     return
    print_thread(b_num, search_term, False, False)
    if is_same_tabpage('view', search_term):
        vim.command('call s:open_mail()')


def notmuch_thread():
    msg_id = get_msg_id()
    if msg_id == '':
        return
    DBASE.open(PATH)
    thread_id = DBASE.find_message(msg_id).get_thread_id()
    DBASE.close()
    search_term = 'thread:' + thread_id
    notmuch_search([0, 0, search_term])  # 戦闘2つの0はダミーデータ
    vim.command('normal! zO')
    index = [i for i, msg in enumerate(
        THREAD_LISTS[search_term]) if msg.get_message_id() == msg_id]
    vim.current.window.cursor = (index[0]+1, 0)


GLOBALS = globals()

initialize()
