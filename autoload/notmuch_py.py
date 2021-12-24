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
from subprocess import Popen, PIPE, run, TimeoutExpired  # API で出来ないことは notmuch コマンド
import os                           # ディレクトリの存在確認、作成
import shutil                       # ファイル移動
import sys                          # プロセス終了
import datetime                     # 日付
import re                           # 正規表現
import glob                         # ワイルドカード展開
from operator import attrgetter     # ソート
# from operator import itemgetter, attrgetter  # ソート
import copy


def print_warring(msg):
    if VIM_MODULE:
        vim.command('redraw | echohl WarningMsg | echomsg "' + msg.replace('"', '\\"') + '" | echohl None')
    else:
        sys.stderr.write(msg)


def print_err(msg):  # エラー表示だけでなく終了
    if VIM_MODULE:
        vim.command('echohl ErrorMsg | echomsg "' + msg.replace('"', '\\"') + '" | echohl None')
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
# スレッド・リスト・データの辞書
# search_term がキーで、アイテムが次の辞書になっている
# list: メール・データ
# sort: ソート方法
# make_sort_key: デフォルト・ソート方法以外のソートに用いるキーを作成済みか?
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
        self._date = msg.get_date()                   # 日付 (time_t)
        self._newest_date = thread.get_newest_date()  # 同一スレッド中で最も新しい日付 (time_t)
        self._thread_id = thread.get_thread_id()      # スレッド ID
        self._thread_order = order                    # 同一スレッド中の表示順
        self.__thread_depth = depth                   # 同一スレッド中での深さ
        self._msg_id = msg.get_message_id()           # Message-ID
        # self._authors = ''                            # 同一スレッド中のメール作成者 (初期化時はダミーの空文字)
        # self._thread_subject = ''                     # スレッド・トップの Subject (初期化時はダミーの空文字)
        self.__subject = msg.get_header('Subject')
        self._from = RE_TAB2SPACE.sub(' ', email2only_name(msg.get_header('From'))).lower()
        # self.__path = msg.get_filenames().__str__().split('\n')  # file name (full path)
        # ↑同一 Message-ID メールが複数でも取り敢えず全て
        # 整形した日付
        self.__reformed_date = RE_TAB2SPACE.sub(
            ' ', datetime.datetime.fromtimestamp(self._date).strftime(DATE_FORMAT))
        # 整形した Subject
        self._reformed_subject = RE_TAB2SPACE.sub(
            ' ', RE_END_SPACE.sub('', RE_SUBJECT.sub('', self.__subject)))
        # 整形した宛名
        m_from = msg.get_header('From')
        try:
            m_to = msg.get_header('To')
        except notmuch.errors.NullPointerError:  # どの様な条件で起きるのか不明なので、取り敢えず From ヘッダを使う
            if VIM_MODULE:
                print_warring('Message-ID:' + self._msg_id +
                              'notmuch.errors.NullPointerError')
            else:
                print('Message-ID:' + self._msg_id +
                      'notmuch.errors.NullPointerError')
            m_to = m_from
        # ↓From, To が同一なら From←名前が入っている可能性がより高い
        m_to_adr = email2only_address(m_to)
        m_from_name = email2only_name(m_from)
        if m_to_adr == email2only_address(m_from):
            name = RE_TAB2SPACE.sub(' ', m_from_name)
        else:  # それ以外は送信メールなら To だけにしたいので、リスト利用
            tagslist = list(msg.get_tags())
            # 実際の判定 (To と Reply-To が同じなら ML だろうから除外)
            if SENT_TAG in tagslist \
                    and m_to_adr != email2only_address(msg.get_header('Reply-To')) \
                    and m_to != '':
                name = 'To:'+email2only_name(m_to)
            else:
                name = RE_TAB2SPACE.sub(' ', m_from_name)
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

    def get_list(self, flag_thread):
        ls = ''
        for item in DISPLAY_ITEM:
            if item == 'date':
                ls += self.__reformed_date+'\t'
            elif item == 'subject':
                subject = self.__thread_depth * flag_thread *\
                    (' '+'\t')+self._reformed_subject
                if item != DISPLAY_ITEM[-1]:  # 最後でない時は長さを揃えるために空白で埋める
                    ls += str_just_length(subject, SUBJECT_LENGTH)+'\t'
                else:
                    ls += subject+'\t'
            elif item == 'from':
                if item != DISPLAY_ITEM[-1]:  # 最後でない時は長さを揃えるために空白で埋める
                    ls += str_just_length(
                            RE_TAB2SPACE.sub(' ', self.__reformed_name), FROM_LENGTH)+'\t'
                else:
                    ls += RE_TAB2SPACE.sub(
                            ' ', RE_END_SPACE.sub('', self.__reformed_name))+'\t'
            else:
                print_err("Don't add '" + item + "' element in thread list.  Reset g:notmuch_display_item.")
        return RE_END_SPACE.sub('', ls)

    def make_sort_key(self):
        query = notmuch.Query(DBASE, 'id:"' + self._msg_id + '"')
        thread = list(query.search_threads())[0]
        # 同一スレッド中のメール作成者
        string = thread.get_authors()
        if string is None:
            self._authors = ''
        else:
            self._authors = ','.join(sorted([RE_TOP_SPACE.sub('', s)
                                     for s in re.split('[,|]', string.lower())]))
            # ↑おそらく | で区切られているのは、使用している search_term では含まれれないが、同じ thread_id に含まれているメールの作成者
        # スレッド・トップの Subject
        string = list(thread.get_toplevel_messages())[0].get_header('Subject')
        if string is None:
            self._thread_subject = ''
        else:
            self._thread_subject = RE_TAB2SPACE.sub(
                ' ', RE_END_SPACE.sub('', RE_SUBJECT.sub('', string)))

    def get_date(self): return self.__reformed_date

    def get_subject(self): return self.__subject

    def set_subject(self, s):  # 復号化した時に呼び出され、Subject 情報を書き換える
        self._reformed_subject = RE_TAB2SPACE.sub(
                            ' ', RE_END_SPACE.sub('', RE_SUBJECT.sub('', s)))
        self.__subject = s


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
    elif VIM_MODULE:  # notmuch new の結果をクリア←redraw しないとメッセージが表示されるので、続けるためにリターンが必要
        vim.command('redraw')
    make_dir(ATTACH_DIR)
    make_dir(TEMP_DIR)
    rm_file(ATTACH_DIR)
    rm_file(TEMP_DIR)
    DBASE = notmuch.Database()
    DBASE.close()


def make_dump():
    if vim.vars.get('notmuch_make_dump', 0):
        make_dir(TEMP_DIR)
        ret = run(['notmuch', 'dump', '--gzip', '--output=' + TEMP_DIR + 'notmuch.gz'],
                  stdout=PIPE, stderr=PIPE)
        if ret.returncode:
            print(ret.stderr.decode('utf-8'))
        else:
            shutil.move(TEMP_DIR + 'notmuch.gz', get_save_dir() + 'notmuch.gz')
    rm_file(ATTACH_DIR)
    rm_file(TEMP_DIR)
    delete_gloval_variable()


def make_dir(dirname):
    if not os.path.isdir(dirname):
        os.mkdir(dirname)
        os.chmod(dirname, 0o700)


def notmuch_new(open_check):
    # # メールを開いているとスワップファイルが有るので、データベースの再作成に失敗する
    # # →open_check が True なら未保存バッファが有れば、そちらに移動し無ければバッファを完全に閉じる
    # if VIM_MODULE and open_check:
    #     if opened_mail(False):
    #         print_warring('Can\'t remake database.\rBecase open the file.')
    #         return False
    #     # return True
    return shellcmd_popen(['notmuch', 'new'])


def opened_mail(draft):  # メールボックス内のファイルが開かれているか?
    # draft フォルダもチェック対象にするか?
    # 未保存なら、そのバッファに移動/開き True を返す
    # 全て保存済みならバッファから削除し False を返す
    for info in vim.eval('getbufinfo()'):
        filename = info['name']
        if draft:
            if MAILBOX_TYPE == 'Maildir':
                draft_dir = PATH + os.sep + '.draft'
            else:
                draft_dir = PATH + os.sep + 'draft'
            if filename.startswith(draft_dir + os.sep):
                continue
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
    print_warring(ret.stderr.decode('utf-8'))
    return True


def make_thread_core(search_term):
    from concurrent import futures

    query = notmuch.Query(DBASE, search_term)
    try:  # スレッド一覧
        threads = query.search_threads()
    except notmuch.errors.NullPointerError:
        print_err('Error: Search thread')
        return False
    if VIM_MODULE:
        reprint_folder()  # 新規メールなどでメール数が変化していることが有るので、フォルダ・リストはいつも作り直す
        print('Making cache data:'+search_term)
    else:  # vim 以外では途中経過の表示なので標準出力ではなくエラー出力に
        sys.stderr.write('Making cache data: '+search_term+'\n')
    threads = [i.get_thread_id() for i in threads]  # 本当は thread 構造体のままマルチプロセスで渡したいが、それでは次のように落ちる
    # ValueError: ctypes objects containing pointers cannot be pickled
    ls = []
    # with futures.ProcessPoolExecutor(max_workers=os.cpu_count()) as executor:  # ←変化なし
    # with futures.ThreadPoolExecutor() as executor:  # ←落ちる
    with futures.ProcessPoolExecutor() as executor:  # ProcessPoolExecutor
        f = [executor.submit(make_single_thread, i, search_term) for i in threads]
        # r = [r.result() for r in f]
        # ls = list(itertools.chain.from_iterable([r.result() for r in f]))  # 遅い
        # for r in futures.as_completed(f):
        for r in f:
            ls += r.result()
    # for i in threads:
    #     ls += make_single_thread(i, search_term)
    ls.sort(key=attrgetter('_newest_date', '_thread_id', '_thread_order'))
    THREAD_LISTS[search_term] = {'list': ls, 'sort': ['date'], 'make_sort_key': False}
    if VIM_MODULE:
        vim.command('redraw')
    return True


def make_single_thread(thread_id, search_term):
    def make_reply_ls(ls, message, depth):  # スレッド・ツリーの深さ情報取得
        ls.append((message.get_message_id(), message, depth))
        for msg in message.get_replies():
            make_reply_ls(ls, msg, depth+1)

    query = notmuch.Query(DBASE, '('+search_term+') and thread:'+thread_id)
    thread = list(query.search_threads())[0]  # thread_id で検索しているので元々該当するのは一つ
    try:  # スレッドの深さを調べる為のリスト作成開始 (search_term に合致しないメッセージも含まれる)
        msgs = thread.get_toplevel_messages()
    except notmuch.errors.NullPointerError:
        print_err('Error: get toplevel message')
    replies = []
    for msg in msgs:
        make_reply_ls(replies, msg, 0)
    order = 0
    ls = []
    # search_term にヒットするメールに絞り込み
    for reply in replies:
        if notmuch.Query(DBASE, '(' + search_term +
                         ') and id:"' + reply[0] + '"').count_messages():
            depth = reply[2]
            if depth > order:
                depth = order
            ls.append(MailData(reply[1], thread, order, depth))
            order = order+1
    return ls


def set_folder_format():
    global FOLDER_FORMAT
    try:
        DBASE.open(PATH)
    except NameError:
        DBASE.close()
        return False
    a = len(str(int(notmuch.Query(DBASE, 'path:**').count_messages() * 1.2)))  # メール総数
    u = len(str(int(notmuch.Query(DBASE, 'tag:unread').count_messages())))+1
    f = len(str(int(notmuch.Query(DBASE, 'tag:flagged').count_messages())))+1
    # 末尾付近の↑ * 1.2 や + 1 は増加したときのために余裕を見ておく為
    DBASE.close()
    max_len = 0
    for s in vim.vars['notmuch_folders']:
        s_len = len(s[0].decode())
        if s_len > max_len:
            max_len = s_len
    vim.command('call s:set_open_way(' + str(max_len + a + u + f + 5) + ')')
    if 'notmuch_folder_format' in vim.vars:
        FOLDER_FORMAT = vim.vars['notmuch_folder_format'].decode()
    else:
        FOLDER_FORMAT = '{0:<' + str(max_len) + '} {1:>' + str(u) + '}/{2:>' + \
            str(a) + '}|{3:>' + str(f) + '} [{4}]'
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
    set_folder_b_vars(b.vars['notmuch'])
    DBASE.close()
    # vim.command('redraw')


def reprint_folder():
    # フォルダ・リストの再描画 (print_folder() の処理と似ているが、b[:] = None して書き直すとカーソル位置が変わる)
    # s:start_notmuch() が呼ぼれずに mail-new がされていると s:buf_num が未定義なので直ちに処理を返す
    if not ('buf_num' in vim.bindeval('s:')):
        return
    if not ('folders' in vim.bindeval('s:buf_num')):
        return
    b = vim.buffers[vim.bindeval('s:buf_num')['folders']]
    b.options['modifiable'] = 1
    for i, folder_way in enumerate(vim.vars['notmuch_folders']):
        folder = folder_way[0].decode()
        search_term = folder_way[1].decode()
        if search_term != '':
            b[i] = format_folder(folder, search_term)
    b.options['modifiable'] = 0
    set_folder_b_vars(b.vars['notmuch'])
    vim.command('redrawstatus!')


def reprint_folder2():
    notmuch_new(False)
    DBASE.open(PATH)
    reprint_folder()
    DBASE.close()


def set_folder_b_vars(v):  # フォルダ・リストのバッファ変数セット
    v['all_mail'] = notmuch.Query(DBASE, '').count_messages()
    v['unread_mail'] = notmuch.Query(DBASE, 'tag:unread').count_messages()
    v['flag_mail'] = notmuch.Query(DBASE, 'tag:flagged').count_messages()


def rm_file(dirname):  # ファイルやディレクトリをワイルドカードで展開して削除
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
    if not (search_term in THREAD_LISTS.keys()):
        DBASE.open(PATH)
        if not make_thread_core(search_term):
            DBASE.close()
            return False
        DBASE.close()
    if 'list' in THREAD_LISTS[search_term]['sort']:
        for msg in THREAD_LISTS[search_term]['list']:
            print(msg.get_list(False))
    else:
        for msg in THREAD_LISTS[search_term]['list']:
            print(msg.get_list(True))
    return True


def get_unread_in_THREAD_LISTS(search_term):  # THREAD_LISTS から未読を探す
    return [i for i, x in enumerate(THREAD_LISTS[search_term]['list'])
            if (DBASE.find_message(x.get_message_id()) is not None)  # 削除済みメール・ファイルがデータベースに残っていると起きる
            and ('unread' in DBASE.find_message(x.get_message_id()).get_tags())]


def open_thread(line, select_unread, remake):  # フォルダ・リストからスレッドリストを開く
    folder, search_term = vim.vars['notmuch_folders'][line - 1]
    folder = folder.decode()
    search_term = search_term.decode()
    if not check_search_term(search_term):
        return
    b_num = vim.bindeval('s:buf_num')['thread']
    if folder == '':
        vim.command('call sign_unplace("mark_thread", {"name": "notmuch", "buffer": ' + str(b_num) + ', })')
        b = vim.buffers[b_num]
        b.options['modifiable'] = 1
        b[:] = None
        b.options['modifiable'] = 0
        b_v = b.vars['notmuch']
        b_v['search_term'] = ''
        b_v['tags'] = ''
        b_v['pgp_result'] = ''
        return
    if search_term == '':
        vim.command('call win_gotoid(bufwinid(s:buf_num["folders"]))')
        notmuch_search([])
    b_v = vim.current.buffer.vars['notmuch']
    if vim.bindeval('win_gotoid(bufwinid(' + str(b_num) + '))') \
            and not remake \
            and ('search' in b_v) \
            and b_v['search_term'].decode() == search_term:
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
    if remake or not (search_term in THREAD_LISTS):
        if not make_thread_core(search_term):
            return
        threadlist = THREAD_LISTS[search_term]['list']
    else:
        threadlist = THREAD_LISTS[search_term]['list']
    b.options['modifiable'] = 1
    flag = not ('list' in THREAD_LISTS[search_term]['sort'])
    # vim.command('setlocal syntax=off foldmethod=manual')
    # マルチプロセスだと、vim.buffers[num] や vim.current.buffer.number だとプロセスが違うので、異なる数値になり上手くいかない
    # 速くならない
    # count = len(threadlist)
    # j = count - vim.bindeval('getbufinfo(' + str(b_num) + ')')[0]['linecount']
    # if j > 0:
    #     ls = [''] * j
    #     b.append(ls)
    # b.vars['notmuch']['search_term'] = search_term
    # from concurrent import futures
    # with futures.ThreadPoolExecutor() as executor:
    #     for i, msg in enumerate(threadlist):
    #         executor.submit(print_thread_line, b, i, msg, flag)
    # b[count:] = None
    # 出力部分の作成だけマルチプロセス化するバージョン←やはり速くならない
    # with futures.ThreadPoolExecutor() as executor:
    #     f = [executor.submit(make_thread_line, msg, i, flag) for i, msg in enumerate(threadlist)]
    #     for r in f:
    #         ret = r.result()
    #         b[ret[0]] = ret[1]
    # b[count:] = None
    # マルチスレッド化しないバージョン
    b.vars['notmuch']['search_term'] = search_term
    b[:] = None
    ls = []
    for msg in threadlist:
        ls.append(msg.get_list(flag))
    # 下の様はマルチプロセス化を試みたが反って遅くなる
    # with futures.ProcessPoolExecutor() as executor:  # ProcessPoolExecutor
    #     f = [executor.submit(i.get_list, flag) for i in threadlist]
    #     for r in f:
    #         ls.append(r.result())
    b.append(ls)
    b[0] = None
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
            vim.command('normal! Gz-')
            vim.command('call s:fold_open()')


def make_thread_line(msg, i, flag):
    return (i, msg.get_list(flag))


def print_thread_line(b, i, msg, flag):
    b[i] = msg.get_list(flag)
    return


def thread_change_sort(sort_way):
    msg_id = get_msg_id()
    if msg_id == '':
        return
    b = vim.current.buffer
    if not ('search_term' in b.vars['notmuch']):
        return
    bufnr = b.number
    search_term = b.vars['notmuch']['search_term'].decode()
    if search_term == '':
        return
    if bufnr != vim.bindeval('s:buf_num')['thread'] \
            and not (search_term in vim.bindeval('s:buf_num')['search']
                     and bufnr == vim.bindeval('s:buf_num')['search'][search_term]):
        return
    sort_way = sort_way[2:]
    while True:
        ls = sorted(list(set(sort_way)))
        sort_way = []
        for i in ls:
            if i in ['list', 'tree', 'Date', 'date', 'From', 'from', 'Subject', 'subject']:
                sort_way.append(i)
            else:
                print_warring('No sorting way: ' + i)
        if (len(sort_way) > 2
                or (not ('tree' in sort_way) and not ('list' in sort_way) and len(sort_way) > 1)
                or (('tree' in sort_way) and ('list' in sort_way))):
            sort_way = ' '.join(sort_way)
            print_warring('Too many arguments: ' + sort_way)
            sort_way = vim.eval(
                'input("sorting_way: ", "' + sort_way + '", "customlist,Complete_sort_input")'
                ).split()
            if sort_way == []:
                return
        elif sort_way == []:
            sort_way = vim.eval(
                'input("sorting_way: ", "", "customlist,Complete_sort_input")'
                ).split()
            if sort_way == []:
                return
        else:
            break
    if sort_way == ['list']:
        if 'list' in THREAD_LISTS[search_term]['sort']:
            return  # 結局同じ表示方法
        else:
            sort_way.extend(THREAD_LISTS[search_term]['sort'])
    elif sort_way == ['tree']:
        sort_way = copy.deepcopy(THREAD_LISTS[search_term]['sort'])
        if 'list' in sort_way:
            sort_way.remove('list')
        else:
            return  # 結局同じ表示方法
    elif 'tree' in sort_way:
        sort_way.remove('tree')
    if sort_way == THREAD_LISTS[search_term]['sort']:
        return
    vim.command('call sign_unplace("mark_thread", {"name": "notmuch", "buffer": ' + str(bufnr) + ', })')
    if not THREAD_LISTS[search_term]['make_sort_key']:
        DBASE.open(PATH)
        for msg in THREAD_LISTS[search_term]['list']:
            msg.make_sort_key()
        DBASE.close()
        THREAD_LISTS[search_term]['make_sort_key'] = True
    if 'list' in sort_way:
        if 'Subject' in sort_way:
            THREAD_LISTS[search_term]['list'].sort(
                key=attrgetter('_reformed_subject'), reverse=True)
        elif 'subject' in sort_way:
            THREAD_LISTS[search_term]['list'].sort(
                key=attrgetter('_reformed_subject'))
        elif 'Date' in sort_way:
            THREAD_LISTS[search_term]['list'].sort(
                key=attrgetter('_date'), reverse=True)
        elif 'date' in sort_way:
            THREAD_LISTS[search_term]['list'].sort(
                key=attrgetter('_date'))
        elif 'From' in sort_way:
            THREAD_LISTS[search_term]['list'].sort(
                key=attrgetter('_from'), reverse=True)
        elif 'from' in sort_way:
            THREAD_LISTS[search_term]['list'].sort(
                key=attrgetter('_from'))
        else:
            THREAD_LISTS[search_term]['list'].sort(
                key=attrgetter('_date'))
        threadlist = THREAD_LISTS[search_term]['list']
    else:
        threadlist = sorted(THREAD_LISTS[search_term]['list'],
                            key=attrgetter('_thread_id', '_thread_order'))
        if 'Subject' in sort_way:
            threadlist.sort(key=attrgetter('_thread_subject'), reverse=True)
        elif 'subject' in sort_way:
            threadlist.sort(key=attrgetter('_thread_subject'))
        elif 'Date' in sort_way:
            threadlist.sort(key=attrgetter('_newest_date'), reverse=True)
        elif 'date' in sort_way:
            threadlist.sort(key=attrgetter('_newest_date'))
        elif 'From' in sort_way:
            threadlist.sort(key=attrgetter('_authors'), reverse=True)
        elif 'from' in sort_way:
            threadlist.sort(key=attrgetter('_authors'))
        else:
            threadlist.sort(key=attrgetter('_newest_date'))
        THREAD_LISTS[search_term]['list'] = threadlist
    THREAD_LISTS[search_term]['sort'] = sort_way
    b.options['modifiable'] = 1
    flag = not ('list' in sort_way)
    # マルチスレッド 速くならない
    # with futures.ThreadPoolExecutor() as executor:
    #     for i, msg in enumerate(threadlist):
    #         executor.submit(print_thread_line, b, i, msg, flag)
    # マルチスレッドしていないバージョン
    b[:] = None
    ls = []
    for msg in threadlist:
        ls.append(msg.get_list(flag))
    b.append(ls)
    b[0] = None
    b.options['modifiable'] = 0
    index = [i for i, msg in enumerate(threadlist) if msg.get_message_id() == msg_id]
    vim.command('normal! Gz-')
    if len(index):  # 実行前のメールがリストに有れば選び直し
        vim.current.window.cursor = (index[0]+1, 0)
    else:
        print('Don\'t select same mail.\nBecase already Delete/Move/Change folder/tag.')
        vim.command('normal! G')
    vim.command('call s:fold_open()')


def change_buffer_vars():  # スレッド・リストのバッファ変数更新
    DBASE.open(PATH)
    change_buffer_vars_core()
    DBASE.close()
    vim.command('redrawstatus!')


def change_buffer_vars_core():
    b_v = vim.current.buffer.vars['notmuch']
    b_v['pgp_result'] = ''
    if vim.current.buffer[0] == '':  # ←スレッドなので最初の行が空か見れば十分
        b_v['msg_id'] = ''
        b_v['subject'] = ''
        b_v['date'] = ''
        b_v['tags'] = ''
    else:
        msg = THREAD_LISTS[b_v['search_term'].decode()]['list'][vim.current.window.cursor[0]-1]
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
    b_v = b.vars['notmuch']
    open_mail_by_msgid(b_v['search_term'].decode(),
                       b_v['msg_id'].decode(), str(b.number), True)
    DBASE.close()


def reload_thread():
    # if opened_mail(False):
    #     print_warring('Please save and close mail.')
    #     return
    b = vim.current.buffer
    search_term = b.vars['notmuch']['search_term'].decode()
    notmuch_new(False)
    w = vim.current.window
    # 再作成後に同じメールを開くため Messag-ID を取得しておく
    msg_id = get_msg_id()
    DBASE.open(PATH)  # ここで書き込み権限 ON+関数内で OPEN のままにしたいが、そうすると空のスレッドで上の
    # search_term = b.vars['notmuch']['search_term'].decode()
    # で固まる
    print_thread_core(b.number, search_term, False, True)
    if msg_id != '':
        index = [i for i, msg in enumerate(
            THREAD_LISTS[search_term]['list']) if msg.get_message_id() == msg_id]
    # else:  # 開いていれば notmuch-show を一旦空に←同一タブページの時は vim script 側メールを開くので不要
    # ただし、この関数内でその処理をすると既読にしてしまいかねないので、ここや print_thread() ではやらない
    if b[0] == '':  # リロードの結果からのスレッド空←スレッドなので最初の行が空か見れば十分
        if 'show' in vim.bindeval('s:buf_num'):
            empty_show()
        return
    # ウィンドウ下部にできるだけ空間表示がない様にする為一度最後のメールに移動後にウィンドウ最下部にして表示
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
                    THREAD_LISTS[search_term]['list'][w.cursor[0] - 1].get_message_id(),
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
    threadlist = THREAD_LISTS[search_term]['list']
    msg_id = threadlist[index].get_message_id()
    open_mail_by_msgid(search_term, msg_id, active_win, False)
    DBASE.close()


def open_mail_by_msgid(search_term, msg_id, active_win, mail_reload):
    # スレッド・リストの順番ではなく Message_ID によってメールを開く
    # 開く前に呼び出し元となるバッファ変数保存
    def check_end_view():  # メール終端まで表示しているか?
        if vim.bindeval('line("w$")') == len(vim.current.buffer):  # 末尾まで表示
            # ただしメールなので、行が長く折り返されて表示先頭行と最終行が同一の場合は考慮せず
            return True
        else:
            return False

    def get_msg():  # 条件を満たす Message とそのメール・ファイル名を取得
        # ファイルが全て消されている場合は、None, None を返す
        b_v['search_term'] = search_term
        msg = list(notmuch.Query(
            DBASE, '('+search_term+') and id:"' + msg_id + '"').search_messages())
        if len(msg):
            msg = msg[0]
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
        try:
            b_v['subject'] = msg.get_header('Subject')
        except notmuch.errors.NullPointerError:  # メール・ファイルが削除されているときに起きる
            b_v['subject'] = ''
        b_v['date'] = RE_TAB2SPACE.sub(
            ' ', datetime.datetime.fromtimestamp(msg.get_date()).strftime(DATE_FORMAT))
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
        return None, None

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
                    n = str(len(vim.current.buffer))
                    vim.command(n+','+n+'fold')

    def print_virtual_header(header):
        attachments = msg_file.get_all(header)
        if attachments is None:
            return
        b = vim.current.buffer
        for f in attachments:
            f = decode_header(f)
            f = os.path.expandvars(os.path.expanduser(f))
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
            if f == '':
                continue
            elif os.path.isfile(f):
                header = 'Attach: '
                b_attachments[str(len(vim.current.buffer))] = [name, [-1], tmp_dir]
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
                 re.sub(r'(\f.+\f)', r'\n\1\n',
                        s.replace('\r\n', '\n').replace('\x1c', '\f'))))
        while b[-1] == '':
            b[-1] = None

    def get_mail_context(part, charset, encoding):  # メールの本文をデコードして取り出す
        if charset == 'gb2312':  # Outlook からのメールで実際には拡張された GBK や GB 1830 を使っているのに
            # Content-Type: text/plain; charset="gb2312"
            # で送ってくるのに対する対策
            # https://ifritjp.github.io/blog/site/2019/02/07/outlook.html
            # http://sylpheed-support.good-day.net/bbs_article.php?pthread_id=744
            # 何故か日本語メールもこの gb2312 として送られてくるケースも多い
            charset = 'gb18030'  # 一律最上位互換の文字コード GB 1830 扱いにする
        # elif charset == 'iso-2022-jp':
        #     charset = 'iso-2022-jp-3'
        #     print(charset)
        # 他には iso-2022-jp-2004, iso-2022-jp-ext があるがどれもだめなので nkf を使う
        if encoding == '8bit' \
                or (charset == 'utf-8' and encoding is None):  # draft メールで encoding 情報がない場合
            payload = part.get_payload()
            return payload, payload
        else:
            payload = part.get_payload(decode=True)
            undecode_payload = part.get_payload(decode=False)
            line = re.split('[\n\r]', re.sub(r'[\s\n]+$', '', undecode_payload))
            pgp_sig = line[0] == '-----BEGIN PGP SIGNED MESSAGE-----' \
                and line[-1] == '-----END PGP SIGNATURE-----'
            if pgp_sig:
                b_con = line.index('')
                b_sig = line.index('-----BEGIN PGP SIGNATURE-----')
                if encoding == 'base64':  # PGP 署名で本文のみが base64 の場合 (本当にあるかどうか不明)
                    from base64 import b64decode
                    content = '\n'.join(line[0:b_con]) + \
                        b64decode('\n'.join(line[b_con:b_sig])).decode(charset) + \
                        '\n'.join(line[b_sig:])
                    return content, undecode_payload
                elif encoding == 'quoted-printable':
                    from quopri import decodestring
                    content = '\n'.join(line[0:b_con]) + \
                        decodestring('\n'.join(line[b_con:b_sig])).decode(charset) + \
                        '\n'.join(line[b_sig:])
                    return content, undecode_payload
            if encoding == 'base64':
                decode_payload = payload.decode()
            else:
                decode_payload = undecode_payload
            try:
                return payload.decode(charset), decode_payload
            except UnicodeDecodeError:
                if shutil.which('nkf') is None or charset != 'iso-2022-jp':
                    return payload.decode(charset, 'replace'), decode_payload
                else:
                    ret = run(['nkf', '-w', '-J'], input=payload, stdout=PIPE)
                    return ret.stdout.decode(), decode_payload
            except LookupError:
                print_warring('unknon encoding ' + charset + '.')
                payload = part.get_payload()
                return payload, decode_payload

    def print_attach_header(part, part_ls, header, name):
        if type(part.get_payload()) == list:  # is_multipart() == True で呼び出されている (message/rfc822 の場合)
            if is_delete_rfc(part):
                vim.current.buffer.append('Del-' + header+name)
                return
        elif part.get_payload() == '':
            vim.current.buffer.append('Del-' + header+name)
            return
        if len(part_ls) >= 2:
            b_attachments[str(len(vim.current.buffer))] = [name, part_ls, part.as_string()]
        else:
            b_attachments[str(len(vim.current.buffer))] = [name, part_ls, '']
        vim.current.buffer.append(header+name)

    def select_header(part, part_ls, part_num, pre_part, pgp):
        ls = vim.List(part_ls)
        ls.extend([part_num])
        attachment = decode_header(part.get_filename())
        name = ''
        for t in part.get_params():
            if t[0] == 'name':
                name = decode_header(t[1])
                break
        if len(attachment) < len(name):
            attachment = name
        signature = ''
        inline = is_inline(part)
        content_type = part.get_content_type().lower()
        if pgp:
            header = 'Encrypt: '
            if attachment == '':
                attachment = 'message.asc'
            ls.extend([-1])
            if inline:
                signature = part.get_payload()
        elif content_type == 'application/pgp-keys':
            header = 'PGP-Public-Key: '
            if attachment == '':
                attachment = 'public_key.asc'
        elif content_type != 'application/pgp-signature' \
                and content_type != 'application/x-pkcs7-signature' \
                and content_type != 'application/pkcs7-signature':
            header = 'Attach: '
            if attachment == '':
                attachment = 'attachment'
        else:
            if content_type == 'application/pgp-signature':
                cmd = 'gpg'
                if attachment == '':
                    attachment = 'signature.asc'
            elif content_type == 'application/x-pkcs7-signature' \
                    or content_type == 'application/pkcs7-signature':
                cmd = 'gpgsm'
                if attachment == '':
                    attachment = 'smime.p7s'
            if shutil.which(cmd) is None:
                print_attach_header(part, ls, 'Signature: ', attachment)
                if inline:
                    return '\n\n' + part.get_payload()
                else:
                    return ''
            make_dir(TEMP_DIR)
            pgp_tmp = TEMP_DIR + 'pgp.tmp'
            decrypt_tmp = TEMP_DIR + 'decrypt.tmp'
            with open(decrypt_tmp, 'w', newline="\r\n") as fp:  # 改行コードを CR+LF に統一して保存
                fp.write(pre_part.as_string())
            # with open(decrypt_tmp, 'w') as fp:
            #     fp.write(re.sub(r'(\r\n|\n\r|\n|\r)', r'\r\n', pre_part.as_string()))  # 改行コードを CR+LF に統一
            write_file(part, 1, pgp_tmp)
            # user = email2only_address(msg.get_header('From'))  # ←落ちる
            # user = email2only_address(msg_file.__getitem__('From'))
            # ユーザ指定すると、gpgsm では鍵がないと不正署名扱いになり、gpg だと存在しないユーザー指定しても、実際には構わず署名としてしまう
            # ret = run(cmd, stdout=PIPE, stderr=PIPE)
            # poup_pgp_signature()
            ret = run([cmd, '--verify', pgp_tmp, decrypt_tmp], stdout=PIPE, stderr=PIPE)
            if ret.returncode:
                if ret.returncode == 1:
                    header = 'Bad-Signature: '
                else:
                    header = 'Signature: '
                if inline:  # Content-Disposition: inline では電子署名を本文に表示
                    signature = '\n\n' + part.get_payload()
            else:
                header = 'Good-Signature: '
            # rm_file_core(pgp_tmp)  # 電子署名なので、直ちに削除する必要はない
            # rm_file_core(decrypt_tmp)
            set_pgp_result(b_v, thread_b_v, ret)
        print_attach_header(part, ls, header, attachment)
        return signature

    def get_output(part, part_ls, part_num, pre_part, output, c_type):
        from html2text import HTML2Text     # HTML メールの整形

        content_type = part.get_content_type()
        # メールを単純にファイル保存した時は UTF-8 にしているので、それをインポートしたときのため、仮の値として指定しておく
        charset = part.get_content_charset('utf-8')
        encoding = part.get('Content-Transfer-Encoding')
        if content_type.find('text/plain') == 0:
            tmp_text, decode_payload = get_mail_context(part, charset, encoding)
            tmp_text = re.sub(r'[\s\n]+$', '', tmp_text)  # 本文終端の空白削除
            split = re.split('[\n\r]', tmp_text)
            # PGP/MIME ではなく本文が署名付きの場合
            if split[0] == '-----BEGIN PGP SIGNED MESSAGE-----' and \
                    split[-1].replace('\r', '') == '-----END PGP SIGNATURE-----':
                # poup_pgp_signature()
                ret = run(['gpg', '--verify'],
                          input=re.sub(r'(\r\n|\n\r|\n|\r)', r'\r\n',  # 改行コードを CR+LF に統一,
                                       decode_payload),
                          stdout=PIPE, stderr=PIPE, text=True)
                if ret.returncode:
                    if ret.returncode == 1:
                        vim.current.buffer.append('Bad-Signature: inline')
                    else:
                        vim.current.buffer.append('Signature: inline')
                else:
                    vim.current.buffer.append('Good-Signature: inline')
                set_pgp_result(b_v, thread_b_v, ret)
            # PGP/MIME ではなく本文が暗号化
            elif split[0] == '-----BEGIN PGP MESSAGE-----' and \
                    split[-1] == '-----END PGP MESSAGE-----':
                ret = decrypt_core('gpg', part, 1, 'inline')
                if ret.returncode <= 1:  # ret.returncode == 1 は署名検証失敗でも復号化はできている可能性あり
                    tmp_text = ret.stdout.decode(charset)
            if tmp_text != '' and tmp_text != '\n':
                output[0] += c_type + '\f' + tmp_text
        elif content_type.find('text/html') == 0:
            tmp_text, tmp_tmp = get_mail_context(part, charset, encoding)
            if tmp_text == '':
                if output[2]:  # 2 個目以降があれば連番
                    b.append('Del-HTML: index'+str(output[2])+'.html')
                else:
                    b.append('Del-HTML: index.html')
            else:
                # 最適な設定が定まっていない
                html_converter = HTML2Text()
                # html_converter.table_start = True
                # html_converter.ignore_tables = True
                html_converter.body_width = len(tmp_text)
                output[1] += '\f' + \
                    re.sub(r'[\s\n]+$', '', html_converter.handle(tmp_text))
                if output[2]:  # 2 個目以降があれば連番
                    print_attach_header(part, [part_num], 'HTML: ', 'index'+str(output[2])+'.html')
                else:
                    print_attach_header(part, [part_num], 'HTML: ', 'index.html')
            output[2] += 1
        else:
            output[0] += select_header(part, part_ls, part_num, pre_part, False)
        return output

    def poup_pgp_signature():  # 書名検証に時間がかかるので、その間ポップ・アップを表示したいがうまく行かない←ウィンドウが切り替わった時点で消えるため
        if vim.bindeval('has("popupwin")'):
            vim.command('call popup_atcursor(["Checking signature"]' +
                        ',{' +
                        '"border": [1,1,1,1],' +
                        '"drag": 1,' +
                        '"close": "click",' +
                        '"id": 1024,' +
                        '})')
            # '"minwidth": 400,' +
        else:
            print('Checking signature')

    def is_inline(part):
        disposition = part.get_all('Content-Disposition')
        if disposition is not None:
            for d in disposition:
                if type(d) is str and d.find('inline') != -1:
                    return True
        return False

    def set_pgp_result(b_v, thread_b_v, ret):
        # gpg/gpgsm の処理の成否は stderr に出力され、stdout にはデコードされた内容
        result = ret.stderr
        # print(type(result))
        if type(result) == bytes:
            result = result.decode('utf-8')
        if 'pgp_result' in b_v:  # 暗号化が繰り返されているケースがある
            b_v['pgp_result'] = b_v['pgp_result'].decode() + result
            thread_b_v['pgp_result'] = thread_b_v['pgp_result'].decode() + result
        else:
            b_v['pgp_result'] = result
            thread_b_v['pgp_result'] = result

    def is_delete_rfc(part):
        c_type = part.get_content_type().lower()
        if c_type == 'message/external-body' \
                and part.get('Content-Type').find('access-type=x-mutt-deleted;') != -1:
            subpart = part.get_payload()
            if type(subpart) == list:
                for p in subpart:
                    if p.get_content_type().lower() == 'message/rfc822':
                        return True
        elif c_type == 'message/rfc822':
            subpart = part.get_payload()
            if type(subpart) == list:
                is_delete = False
                for p in subpart:
                    subsub = p.get_payload()
                    if type(subsub) == list:
                        for subp in subsub:
                            is_delete = is_delete or is_delete_rfc(subp)
                    else:
                        is_delete = is_delete or (len(subsub) == 0)
                return is_delete
            else:
                return (len(subpart) == 0)
        return False

    def decrypt_core(cmd, part, decode, pgp_info):
        if decode:
            if type(part) == email.message.Message \
                    and part.get_content_type().lower() == 'message/rfc822':
                if type(part.get_payload()) == list:
                    decrypt = ''
                    for p in part.get_payload(decode=False):
                        decrypt += p.as_string()
                else:
                    decrypt = part.get_payload().as_string()
            else:
                decrypt = part.get_payload(decode=True)
        else:
            decrypt = part.get_payload(decode=False)
        ret = run([cmd, '--decrypt'], input=decrypt, stdout=PIPE, stderr=PIPE)
        set_pgp_result(b_v, thread_b_v, ret)
        if ret.returncode <= 1:  # ret.returncode == 1 は署名検証失敗でも復号化はできている可能性あり
            b.append('PGP-Decrypted: ' + pgp_info)
        if ret.returncode:  # 署名未検証/失敗は ret.returncode >= 1 なので else/elif ではだめ
            if ret.returncode == 1:
                b.append('Bad-Signature: ' + pgp_info)
            else:
                b.append('PGP-Encrypted: ' + pgp_info)
        return ret

    def decrypt(cmd, part, part_ls, part_num, pre_part, output, pgp_info):
        if shutil.which(cmd) is None:
            output[0] += select_header(part, part_ls, part_num, pre_part, True)
            pgp_info = ''
            return output
        decode = get_part_deocde(part)
        ret = decrypt_core(cmd, part, decode, pgp_info)
        if ret.returncode <= 1:  # ret.returncode == 1 は署名検証失敗でも復号化はできている可能性あり
            decrypt_msg = email.message_from_string(ret.stdout.decode())
            # ↓本文が UTF-8 そのままだと、BASE64 エンコードされた状態になるので、署名検証に失敗する
            # decrypt_msg = email.message_from_bytes(ret.stdout)
            ls = copy.deepcopy(part_ls)
            ls.append(part_num)
            output = msg_walk(decrypt_msg, output, ls, True)
        if ret.returncode:  # 署名未検証/失敗は ret.returncode >= 1 なので else/elif ではだめ
            output[0] += select_header(part, part_ls, part_num, pre_part, True)
        return output

    def msg_walk(msg_file, output, part_ls, encrypt_flag):
        def decrypt_subject():  # メッセージ全体が暗号化されていると Subject が事実上空なので付け直す
            protected_headers = False
            for s in part.get_all('Content-Type'):
                if s.find('protected-headers') != -1:
                    protected_headers = True
            if not protected_headers:
                return False
            sub = ''
            for s in part.get_all('Subject', ''):
                sub += decode_header(s)
            if sub != '':
                b_v['subject'] = sub
                thread_b_v['subject'] = sub
                index = [i for i, x in enumerate(
                    THREAD_LISTS[search_term]['list']) if x.get_message_id() == msg_id][0]
                THREAD_LISTS[search_term]['list'][index].set_subject(sub)
                s = THREAD_LISTS[search_term]['list'][index].get_list(
                        'list' in THREAD_LISTS[search_term]['sort'])
                if not_search:
                    p_b = vim.buffers[vim.bindeval('s:buf_num')['thread']]
                    # p_s_b = vim.buffers[vim.bindeval('s:buf_num')['show']]
                else:
                    p_b = vim.buffers[vim.bindeval('s:buf_num')['search'][search_term]]
                    # p_s_b = vim.buffers[vim.bindeval('s:buf_num')['view'][search_term]]
                p_b.options['modifiable'] = 1
                p_b[index] = s
                p_b.options['modifiable'] = 0
                i = 1  # 先頭行は後から削除されう空行なので1行ずれている
                for header in vim.vars['notmuch_show_headers']:
                    if header.decode().lower() == 'subject':
                        break
                    i += 1
                b[i] = 'Subject: ' + sub
            return True

        part_num = -1
        pgp_info = ''
        pre_part = None
        pre_rfc = ''
        rfc = ''
        multipart_signed = False  # Content-Type: multipart/signed では次のパートが署名対象
        for part in msg_file.walk():
            if multipart_signed:
                pre_part = part
                multipart_signed = False
            if encrypt_flag and not output[3]:
                output[3] = decrypt_subject()
            part_num += 1
            if pgp_info != '':
                output = decrypt('gpg', part, part_ls, part_num, pre_part,
                                 output, 'OpenPGP/MIME ' + pgp_info)
                pgp_info = ''
                continue
            content_type = part.get_content_type().lower()
            if part.is_multipart() and content_type != 'message/rfc822':
                if content_type == 'multipart/signed' \
                        or content_type == 'application/x-pkcs7-signature' \
                        or content_type == 'application/pkcs7-signature':
                    multipart_signed = True
                else:
                    multipart_signed = False
                if not is_delete_rfc(part):
                    part_num -= 1
                    continue
            # 添付ファイル判定により先にしないと、暗号化部分を添付ファイル扱いとしていないケースに対応できない
            elif content_type == 'application/pgp-encrypted':
                pgp_info, tmp_text = get_mail_context(part, 'utf-8', '')
            elif content_type == 'application/x-pkcs7-mime' \
                    or content_type == 'application/pkcs7-mime':
                output = decrypt('gpgsm', part, part_ls, part_num, pre_part, output, 'S/MIME')
            # text/plain, html 判定より先にしないと、テキストや HTML ファイルの添付ファイルが本文扱いになる
            elif part.get_content_disposition() == 'attachment':
                #     or part.get('Content-Description', '').find('PGP/MIME') == 0:
                #     ↑ content_type == 'application/pgp-encrypted'
                #        content_type == 'application/pkcs7-mime':
                #  の判定を前に持っていったので、不要になった
                output[0] += select_header(part, part_ls, part_num, pre_part, False)
            else:
                if content_type.find('text/') != 0:
                    rfc = '\f' + content_type + ' part'
                else:
                    rfc = ''
                if pre_rfc == 'message/rfc822':
                    output = get_output(part, part_ls, part_num, pre_part, output, rfc)
                else:
                    output = get_output(part, part_ls, part_num, pre_part, output, pre_rfc)
            pre_rfc = rfc
        return output

    not_search = vim.current.buffer.number
    not_search = vim.bindeval('s:buf_num')['thread'] == not_search \
        or vim.bindeval('s:buf_num')['show'] == not_search
    if not_search:
        thread_b_v = vim.buffers[vim.bindeval('s:buf_num')['thread']].vars['notmuch']
    else:
        thread_b_v = vim.buffers[vim.bindeval('s:buf_num')['search'][search_term]].vars['notmuch']
    # ↓thread から移す方法だと、逆に show で next_unread などを実行して別の search_term の thread に写った場合、その thread でのバッファ変数が書き換わらない
    # subject = thread_b_v['subject']
    # date = thread_b_v['date']
    # tags = thread_b_v['tags']
    if not_search:
        vim.command('call s:make_show()')
    else:
        vim.command('call s:make_view(\'' + vim_escape(search_term) + '\')')
    b = vim.current.buffer
    b_v = b.vars['notmuch']
    # b_v['editing'] = True  # カーソル連続移動で落ちるので、対策を考えてみたがうまく行かない
    if msg_id == '' or (mail_reload is False and msg_id == b_v['msg_id'].decode()):
        vim.command('call win_gotoid(bufwinid('+active_win+'))')
        return
    # 以下実際の描画
    b.options['modifiable'] = 1
    b[:] = None
    msg, f = get_msg()
    if msg is None:
        b.append('Already all mail file delete.')
        b.options['modifiable'] = 0
        vim.command('call win_gotoid(bufwinid('+active_win+'))')
        vim.command('redrawstatus!')
        return
    vim.options['guitabtooltip'] = 'tags['+get_msg_tags(msg)+']'
    print_header(vim.vars['notmuch_show_headers'])
    fold_begin = len(vim.current.buffer)  # 後から先頭行を削除するので予め
    print_header(vim.vars['notmuch_show_hide_headers'])
    b_attachments = {}  # vim でバッファ変数として保存しておく次の情報
    # * 添付ファイル名
    # * part番号
    # * 下書きをそのまま送信メールとした時のファイルの保存ディレクトリ
    # vim とやり取りするので辞書のキーは、行番号。item は tapple でなく list
    if fold_begin != len(vim.current.buffer):
        vim.command(str(fold_begin+1)+','+str(len(vim.current.buffer))+'fold')
    try:
        with open(f, 'r') as fp:
            msg_file = email.message_from_file(fp)
    except UnicodeDecodeError:
        # ↓本文が UTF-8 そのままのファイルだと、BASE64 エンコードされた状態になり署名検証に失敗する
        # 普段は上のテキスト・ファイルとして開く
        with open(f, 'rb') as fp:
            msg_file = email.message_from_binary_file(fp)
    # 下書きをそのまま送信メールとした時の疑似ヘッダの印字
    header_line = len(vim.current.buffer)   # 疑似ヘッダ以外の印字終了
    print_virtual_header('X-Attach')
    print_virtual_header('Attach')
    b_v['attachments'] = None
    b_v['pgp_result'] = ''
    output = ['', '', 0, False]  # 出力データ [通常の本文、HTML パート、HTML パートの数, b:notmuch['subject'] の書き換えをしたか?]
    output = msg_walk(msg_file, output, [], False)
    b.append('')  # ヘッダと本文区切り
    if output[0] != '':
        vim_append_content(output[0][1:])
    if output[1] != '':
        fold_begin = len(vim.current.buffer)  # text/plain がある時は折りたたむので開始行記録
        vim_append_content(output[1][1:])
        if output[0] != '':  # 実際に折りたたむ場合
            b.append('\fHTML part\f', fold_begin)
            vim.command(str(fold_begin+1)+','+str(len(vim.current.buffer))+'fold')
    del b[0]
    b.options['modifiable'] = 0
    if header_line == len(vim.current.buffer):  # 本文空
        header_line = 1
    elif b_attachments == {}:
        header_line = header_line + 1
    b_v['attachments'] = b_attachments
    vim.current.window.cursor = (1, 0)  # カーソル位置が画面内だと先頭が表示されない
    vim.command('redraw')  # 本当は redrawstatus の位置にしたいが、上が効かなくなる
    vim.current.window.cursor = (header_line, 0)  # カーソルを添付ファイルや本文位置にセット
    if check_end_view() and ('unread' in msg.get_tags()):
        msg = change_tags_before_core(msg.get_message_id())
        delete_msg_tags(msg, ['unread'])
        change_tags_after_core(msg, True)
    vim.command('call win_gotoid(bufwinid('+active_win+'))')
    vim.command('redrawstatus!')
    # del b_v['editing']  # カーソル連続移動で落ちるので、対策を考えてみたがうまく行かない


def empty_show():
    b = vim.buffers[vim.bindeval('s:buf_num')['show']]
    b.options['modifiable'] = 1
    b[:] = None
    b.options['modifiable'] = 0
    b_v = b.vars['notmuch']
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
    b_v = b.vars['notmuch']
    s_bufnum = vim.bindeval('s:buf_num')
    if not ('folders' in s_bufnum):
        # notmuch-folders に対して :bwipeout が実行され、更新された notmuch-edit/draft が有り
        # s:buf_num['folders'] がない状態になり、notmuch-thread がアクティブだとこの関数が呼ばれることがある
        vim.command('new | only | call s:make_folders_list()')
        reopen('thread', '')
        return ''
    if bufnr == s_bufnum['folders'] or b[0] == '':
        # ↑notmuch-folder に加えて、その以外の notmuch-??? は最初の行が空なら全体が空
        return ''
    f_type = b.options['filetype'].decode()
    if f_type == 'notmuch-edit' or f_type == 'notmuch-draft':
        return b_v['msg_id'].decode()
    try:
        search_term = b_v['search_term'].decode()
    except KeyError:
        return ''
    if f_type != 'notmuch-edit' and f_type != 'notmuch-draft' and search_term == '':
        # search_term が空ならスレッドやメール本文を開いていない
        return ''
    if ('show' in s_bufnum
        and bufnr == s_bufnum['show']) \
        or (search_term in s_bufnum['view']
            and bufnr == s_bufnum['view'][search_term]):
        return b_v['msg_id'].decode()
    elif bufnr == s_bufnum['thread'] \
        or (search_term in s_bufnum['search']
            and bufnr == s_bufnum['search'][search_term]):
        return THREAD_LISTS[search_term]['list'][vim.current.window.cursor[0]-1].get_message_id()
    return ''


def change_tags_before(msg_id):  # タグ変更前の前処理
    DBASE.open(PATH, mode=notmuch.Database.MODE.READ_WRITE)
    return change_tags_before_core(msg_id)


def change_tags_before_core(msg_id):
    msg = DBASE.find_message(msg_id)
    if msg is None:
        print_err('Message-ID: ' + msg_id + ' don\'t find.\nDatabase is broken or emails have been deleted.')
        return None
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
    tags += ['flagged', 'inbox', 'draft', 'passed', 'replied', 'unread', 'Trash', 'Spam']
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
    try:  # 同一 Messag-ID の複数ファイルの移動で起きるエラー対処 (大抵移動は出来ている)
        for tag in tags:
            msg.remove_tag(tag, sync_maildir_flags=True)
    except notmuch.NotInitializedError:
        pass


def add_tags(msg_id, s, args):  # vim から呼び出しで tag 追加
    if args is None:
        return
    tags = args[2:]
    if tags == []:
        tags = vim.eval('input("Add tag: ", "", "customlist,Complete_add_tag_input")')
        tags = tags.split()
    if tags == [] or tags is None:
        return
    if is_draft():
        b_v = vim.current.buffer.vars['notmuch']
        b_tags = b_v['tags'].decode().split(' ')
        for t in tags:
            if not (t in b_tags):
                b_tags.append(t)
        b_v['tags'] = ' '.join(b_tags)
        return
    msg = change_tags_before(msg_id)
    if msg is None:
        return
    add_msg_tags(msg, tags)
    change_tags_after(msg, True)
    return [0, 0] + tags


def delete_tags(msg_id, s, args):  # vim から呼び出しで tag 削除
    if args is None:
        return
    tags = args[2:]
    if tags == []:
        tags = vim.eval('input("Delete tag: ", "", "customlist,Complete_delete_tag_input")')
        tags = tags.split()
    if tags == [] or tags is None:
        return
    if is_draft():
        b_v = vim.current.buffer.vars['notmuch']
        b_tags = b_v['tags'].decode().split(' ')
        for t in tags:
            if t in b_tags:
                b_tags.remove(t)
        b_v['tags'] = ' '.join(b_tags)
        return
    msg = change_tags_before(msg_id)
    if msg is None:
        return
    delete_msg_tags(msg, tags)
    change_tags_after(msg, True)
    return [0, 0] + tags


def toggle_tags(msg_id, s, args):  # vim からの呼び出しで tag をトグル
    if args is None:
        return
    tags = args[2:]
    if tags == []:
        tags = vim.eval('input("Toggle tag: ", "", "customlist,Complete_tag_input")')
        tags = tags.split()
    if tags == []:
        return
    if is_draft():
        b_v = vim.current.buffer.vars['notmuch']
        b_tags = b_v['tags'].decode().split(' ')
        for t in tags:
            if t in b_tags:
                b_tags.remove(t)
            else:
                b_tags.append(t)
        b_v['tags'] = ' '.join(b_tags)
        return
    else:
        msg = change_tags_before(msg_id)
        if msg is None:
            return
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
    if is_draft():
        tags = vim.current.buffer.vars['notmuch']['tags'].decode().split(' ')
    else:
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
    if is_draft():
        for t in vim.current.buffer.vars['notmuch']['tags'].decode().split(' '):
            tags.remove(t)
    else:
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
            if not b.options['filetype'].decode().startswith('notmuch-') \
                    or not ('notmuch' in b.vars):
                continue
            b_v = b.vars['notmuch']
            try:
                b_msg_id = b_v['msg_id'].decode()
            except KeyError:  # notmuch-folder や空のバッファ
                continue
            if msg_id == b_msg_id:
                b_v['tags'] = tags
    reprint_folder()


def next_unread(active_win):  # 次の未読メッセージが有れば移動(表示した時全体を表示していれば既読になるがそれは戻せない)
    def open_mail_by_index(buf_num, index):
        vim.command('call win_gotoid(bufwinid(s:buf_num' + buf_num + '))')
        vim.current.window.cursor = (index+1, 0)
        vim.command('call s:fold_open()')
        if is_same_tabpage('show', '') or is_same_tabpage('view', search_term):
            open_mail_by_msgid(search_term,
                               THREAD_LISTS[search_term]['list'][index].get_message_id(),
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
                               THREAD_LISTS[search_term]['list'][index].get_message_id(),
                               active_win, False)
        if str(vim.bindeval('s:buf_num')['folders']) == active_win:
            # and is_same_tabpage('thread', ''):
            vim.command('call win_gotoid(bufwinid(' +
                        str(vim.bindeval('s:buf_num')['thread'])+'))')
        else:
            vim.command('call win_gotoid(bufwinid('+active_win+'))')
        DBASE.close()
        return True

    if not ('search_term' in vim.current.buffer.vars['notmuch']):
        if vim.current.buffer.number == vim.bindeval('s:buf_num')['folders']:
            msg_id = ''
            active_win = str(vim.bindeval('s:buf_num')['thread'])
            search_term = vim.vars['notmuch_folders'][vim.current.window.cursor[0]-1][1]
        else:
            msg_id = get_msg_id()
            search_term = vim.vars['notmuch_folders'][0][1]
            # vim.bindeval('getbufinfo(s:buf_num["folders"])[0]["lnum"]')
            # は folders が非アクティブだと正確に取得できない
    else:
        msg_id = get_msg_id()
        search_term = vim.current.buffer.vars['notmuch']['search_term']
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
        THREAD_LISTS[search_term]['list']) if x.get_message_id() == msg_id][0]
    indexes = get_unread_in_THREAD_LISTS(search_term)
    # ↑ len(indexes) > 0 なら未読有り
    index = [i for i, i in enumerate(indexes) if i > index]
    if len(index):  # 未読メールが同一スレッド内の後ろに有る
        if search_view:
            open_mail_by_index('["search"][\'' + vim_escape(search_term) + '\']', index[0])
            # open_mail_by_index('["search"][\\\'' + search_term + '\\\']', index[0])
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
            open_mail_by_index('["search"][\'' + vim_escape(search_term) + '\']', index[0])
            # open_mail_by_index('["search"][\\\'' + search_term + '\\\']', indexes[0])
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
    shellcmd_popen(['notmuch', 'reindex', 'id:"' + msg_id + '"'])


def decode_header(f):
    if f is None:  # ファイル名の記述がない
        return ''
    name = ''
    for string, charset in email.header.decode_header(f):
        if charset is None:
            if type(string) is bytes:
                name += string.decode('raw_unicode_escape')
            else:  # デコードされず bytes 型でないのでそのまま
                name += string
        elif charset == 'gb2312':  # Outlook からのメールで実際には拡張された GBK や GB 1830 を使っているのに
            # Content-Type: text/plain; charset="gb2312"
            # で送ってくるのに対する対策
            # filename にも該当するか不明だが、念の為
            charset = 'gb18030'  # 一律最上位互換の文字コード GB 1830 扱いにする
        elif charset == 'unknown-8bit':
            name += string.decode('utf-8')
        else:
            try:
                name += string.decode(charset)
            except UnicodeDecodeError:  # コード外範囲の文字が有る時のエラー
                print_warring('File name has out-of-code range characters.')
                if shutil.which('nkf') is None or charset != 'iso-2022-jp':
                    name += string.decode(charset, 'backslashreplace')
                else:
                    ret = run(['nkf', '-w', '-J'], input=string, stdout=PIPE)
                    name += ret.stdout.decode()
            except Exception:
                name += string.decode('raw_unicode_escape')
    return name.replace('\n', ' ')


def get_part_deocde(part):
    # 添付ファイルでも Context-Type='text/plain' 等のテキストで、Content-Transfer-Encoding=8bit なら取り出し時にデコードの必要なし
    transfer_encoding = part.get('Content-Transfer-Encoding')
    if transfer_encoding is None:
        return 1
    else:
        mime = part.get_content_type().lower()
        if mime == 'message/rfc822':  # message/rfc822 を想定しているが、他や 7bit のケースが有るかは未確認
            return 2
        elif transfer_encoding.lower() != '8bit':
            return 1
        elif mime.find('text') == 0:
            return 0
        else:
            print_err('Error Context-Type: ' + part.get_content_type() + ', ' + transfer_encoding)
            return -1


def get_attach_info(line):
    from hashlib import sha256          # ハッシュ

    b_v = vim.current.buffer.vars['notmuch']
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
    b_attachments = b_v['attachments']
    if line not in b_attachments:
        return None, None, None, None
    name, part_num, dirORmes_str = b_attachments[line]
    name = name.decode('utf-8')
    if name == '':  # 元々ファイル名情報がない場合
        name = 'nonename'
    part_num = [i for i in part_num]
    if part_num == [-1]:
        return name, None, None, dirORmes_str.decode('utf-8')
    global ATTACH_DIR
    tmpdir = ATTACH_DIR + sha256(b_v['msg_id']).hexdigest() + os.sep + str(part_num) + os.sep
    if len(part_num) >= 2:
        dirORmes_str = email.message_from_bytes(dirORmes_str)
        decode = get_part_deocde(dirORmes_str)
        return name, dirORmes_str, decode, tmpdir
    msg_id = b_v['msg_id'].decode()
    DBASE.open(PATH)
    msg = list(notmuch.Query(
        DBASE, '('+search_term+') id:"' + msg_id + '"').search_messages())
    if len(msg):
        msg = list(msg)[0]
    else:  # 同一条件+Message_ID で見つからなくなっているので Message_ID だけで検索
        print('Already Delete/Move/Change folder/tag')
        msg = DBASE.find_message(msg_id)
    with open(msg.get_filename(), 'rb') as fp:
        msg_file = email.message_from_binary_file(fp)
    DBASE.close()
    part_count = 0
    part_num = part_num[0]
    for attach in msg_file.walk():
        if attach.get_content_type().lower() != 'message/rfc822' and attach.is_multipart():
            continue
        if part_num == part_count:
            break
        part_count += 1
    decode = get_part_deocde(attach)
    if decode < 0:
        return None, None, None, None
    return name, attach, decode, tmpdir


def open_attachment(args):  # vim で Attach/HTML: ヘッダのカーソル位置の添付ファイルを開く
    def same_attach(fname):
        fname = fname.decode('utf-8')
        for i, ls in vim.current.buffer.vars['notmuch']['attachments'].items():
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
                if vim.bindeval('foldlevel(".")') != 0:
                    vim.command('normal! za')
                elif b'open' in vim.vars['notmuch_open_way'].keys():
                    name = vim.bindeval('synIDattr(synID(line("."), col("."), 1), "name")').decode()
                    if name != 'mailHeaderEmail' and \
                            (name.find('mailHeader') == 0 or name == 'mailSubject'):
                        return
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
            write_file(attachment, decode, full_path)
        print('open '+filename)
        try:
            ret = run([vim.vars['notmuch_view_attachment'].decode(),
                      full_path], stdout=PIPE, stderr=PIPE, timeout=0.5)
            # timeout の指定がないと、アプリによって終了待ちになる
            if ret.returncode:
                print_warring(ret.stderr.decode('utf-8'))
        except TimeoutExpired:
            pass


def get_top(part, i):   # multipart の最初の情報を取得したいときチェック用
    t = type(part)
    print(t)
    if t == bytes:
        part = part.decode('utf-8', 'replace')
    elif t == email.message.Message:
        part = part.as_string()
    if type(part) == str:
        s = re.sub(r'\r\n', r'\n', re.sub(r'\r', r'\n', part))
        match = re.search(r'\n\n', s)
        if match is not None:
            s = s[match.start()+2:]
        print(s.split('\n')[0])
        if len(s) >= i:
            s = s[:i]
        print('')
        print('\n'.join(s))
    else:
        print(type(part), part)


def write_file(part, decode, save_path):  # 添付ファイルを save_path に保存
    import codecs

    def get_html_charset(part):  # text/html なら HTML の charset を取得する
        html = part.get_content_type()
        if html is None:
            return ''
        elif html.lower() != 'text/html':
            return ''
        else:
            from html.parser import HTMLParser

            class GetCharset(HTMLParser):
                def __init__(self):
                    super().__init__()
                    self.found_headline = False  # 見つかったらTrueになる
                    self.headline_texts = ''  # charset

                def handle_starttag(self, tag, attrs):
                    if self.found_headline:
                        if tag == 'meta':
                            content_type = False
                            for k, v in attrs:
                                if k is None or v is None:
                                    continue
                                k = k.lower()
                                v = v.lower()
                                if k == 'charset':
                                    self.headline_texts = v
                                    return
                                elif k == 'http-equiv' and v == 'content-type':
                                    content_type = True
                                elif content_type and k == 'content':
                                    match = re.match(r'\s*text/html;\s*charset=(.+)', v)
                                    if match is None:
                                        continue
                                    self.headline_texts = match.group(1)
                                    return
                    else:
                        if tag == 'head':
                            self.found_headline = True
                        elif tag == 'body':
                            return
                #
                # def handle_endtag(self, tag):
                #     if tag == 'head':
                #         return  # 高速化効果なし

            html = GetCharset()
            html.feed(codecs.decode(part.get_payload(decode=True)))
            return html.headline_texts

    html = get_html_charset(part)
    if decode == 2:  # 今の所 message/rfc822 を想定
        s = ''
        for p in part.get_payload(decode=False):
            s += p.as_string()
        with open(save_path, 'w') as fp:
            fp.write(s)
    elif html != '':
        charset = part.get_content_charset()
        if charset == 'iso-2022-jp':
            charset = 'iso-2022-jp-3'  # 一律最上位互換の文字コード扱いにする
        elif charset == 'gb2312':
            charset = 'gb18030'  # 一律最上位互換の文字コード GB 1830 扱いにする
        try:
            part = codecs.decode(part.get_payload(decode=True), encoding=charset)
            if html == 'iso-2022-jp':
                html = 'iso-2022-jp-3'  # 一律最上位互換の文字コード扱いにする
            elif html == 'gb2312':
                html = 'gb18030'  # 一律最上位互換の文字コード GB 1830 扱いにする
            with open(save_path, 'wb') as fp:
                fp.write(codecs.encode(part, encoding=html))
        except UnicodeDecodeError:  # iso-2022-jp で JIS 外文字が使われていた時
            # ↓全てをこの decode=False で行うと quoted-printable に対応できない
            part = part.get_payload(decode=False)
            with open(save_path, 'wb') as fp:
                fp.write(codecs.encode(part))
    elif decode:
        if type(part) == email.message.Message \
                and part.get_content_type().lower() == 'message/rfc822':
            if type(part.get_payload()) == list:
                s = ''
                for p in part.get_payload(decode=False):
                    s += p.as_string()
                with open(save_path, 'w') as fp:
                    fp.write(s)
            else:
                with open(save_path, 'w') as fp:
                    fp.write(part.get_payload().as_string())
        else:
            with open(save_path, 'wb') as fp:
                fp.write(part.get_payload(decode=True))
    else:
        with open(save_path, 'w') as fp:
            fp.write(part.get_payload(decode=False))


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
            write_file(attachment, decode, save_path)
        vim.command('redraw')
        print('save '+save_path)


def delete_attachment(args):
    def get_modified_date_form():  # 削除したときに書き込む日付情報
        import time                         # UNIX time の取得
        import locale

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
        if type(part.get_payload()) == list:  # 今の所 message/rfc822 のみ想定
            s = ''
            for p in part.get_payload(decode=False):
                s += p.as_string()
        elif part.get_payload() == '':
            return False
        else:
            s = re.sub(r'[\s\n]+$', '', part.get_payload())
        header = ''
        for key in part.keys():
            key_head = ''
            for h in part.get_all(key):
                key_head = key_head + h
            part.__delitem__(key)
            header += key + ': ' + key_head + '\n'
        c_header = 'message/external-body; access-type=x-mutt-deleted;\n' + \
            '\texpiration="' + m_time + '"; length=' + \
            str(len(s))
        part.__setitem__('Content-Type', c_header)
        part.set_payload(header)
        return True

    def delete_attachment_in_show(args):
        def delete_attachment_only_part(fname, part_num):  # part_num 番目の添付ファイルを削除
            with open(fname, 'r') as fp:
                msg_file = email.message_from_file(fp)
            i = 0
            for part in msg_file.walk():
                if part.is_multipart() and part.get_content_type().lower() != 'message/rfc822':
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
            b_attachments = b_v['attachments']
            if line in b_attachments:
                tmp_name, part_num, tmpdir = b_attachments[line]
                part_num = [i for i in part_num]
                if part_num == [-1]:
                    print_warring('The header is vertulal.')
                elif len(part_num) >= 2:
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
                            delete_attachment_only_part(f, part_num[0])
        DBASE.close()

    def delete_attachment_in_thread(args, search_term):
        # メール本文表示だと未読→既読扱いでタグを変更することが有るので書き込み権限も
        def delete_attachment_all(fname):  # text/plin, text/html 以外の全て添付ファイルを削除
            with open(fname, 'r') as fp:
                msg_file = email.message_from_file(fp)
            content_type = msg_file.get_content_type()
            if content_type == 'multipart/encrypted' \
                    or content_type == 'multipart/signed':
                return
            m_time = get_modified_date_form()
            deleted = False
            can_delete = True
            next_can_delete = True
            for part in msg_file.walk():
                if part.is_multipart() and part.get_content_type().lower() != 'message/rfc822':
                    continue
                content_type = part.get_content_type()
                if part.get_content_type() == 'application/pgp-encrypted':
                    can_delete = False
                    next_can_delete = False
                else:  # 直前が application/pgp-encrypted だと application/oct stream でも削除しない
                    can_delete = next_can_delete
                    next_can_delete = True  # 次は削除して良い可能性有り
                if content_type != 'text/plain' \
                        and content_type != 'text/html' \
                        and content_type != 'application/x-pkcs7-mime' \
                        and content_type != 'application/pkcs7-mime' \
                        and content_type != 'application/x-pkcs7-signature' \
                        and content_type != 'application/pkcs7-signature' \
                        and can_delete:
                    deleted = deleted | delete_attachment_core(part, m_time)
            if deleted:
                with open(fname, 'w') as fp:
                    fp.write(msg_file.as_string())

        DBASE.open(PATH, mode=notmuch.Database.MODE.READ_WRITE)
        args = [int(s) for s in args[0:2]]
        for i in range(args[0], args[1]+1):
            msg_id = THREAD_LISTS[search_term]['list'][i-1].get_message_id()
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
        b_attachments = b.vars['notmuch']['attachments']
        b_v_keys = b_attachments.keys()
        b.options['modifiable'] = 1
        deleted = False
        for k in b_v_keys:
            line = int(k.decode()) - 1
            part_num = [i for i in b_attachments[k][1]]
            if part_num == [-1]:
                deleted = deleted | True
            elif len(part_num) >= 2:
                deleted = deleted | True
            elif b[line].find('Attach:') == 0:
                b[line] = 'Del-' + b[line]
                del b_attachments[k]
        b.options['modifiable'] = 0
        if deleted:
            print_warring('Encripted context or Vertual header don\'t delete.')

    b = vim.current.buffer
    bufnr = b.number
    b_v = b.vars['notmuch']
    search_term = b_v['search_term'].decode()
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
        shellcmd_popen(['notmuch', 'reindex', 'id:"' + msg_id + '"'])
        search_term = vim.current.buffer.vars['notmuch']['search_term'].decode()
        print_thread(bufnr, search_term, False, True)
        index = [i for i, x in enumerate(
            THREAD_LISTS[search_term]['list']) if x.get_message_id() == msg_id]
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
    search_term = bufnr.vars['notmuch']['search_term'].decode()
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
        msg_id = THREAD_LISTS[search_term]['list'][line].get_message_id()
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
            shellcmd_popen(['notmuch', 'reindex', 'id:"' + msg_id + '"'])
    DBASE.close()
    print_thread(bufnr, search_term, False, True)
    index = [i for i, x in enumerate(
        THREAD_LISTS[search_term]['list']) if x.get_message_id() == r_msg_id]
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
                os.path.expanduser(vim.vars['notmuch_save_dir'].decode()))
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
        b_v = b.vars['notmuch']
        f_type = b.options['filetype'].decode()
        if f_type == 'notmuch-draft':
            f = b.name
            lists = ['msg-id     : ' + b_v['msg_id'].decode(),
                     'tags       : ' + b_v['tags'].decode(),
                     'file       : ' + f]
            if os.path.isfile(f):
                lists += ['Modified   : ' +
                          datetime.datetime.fromtimestamp(os.path.getmtime(f)).strftime(DATE_FORMAT),
                          'Size       : ' + str(os.path.getsize(f)) + ' Bytes']
            else:
                lists += ['Modified   : No save']
            return lists
        if bnum == vim.bindeval('s:buf_num')['folders']:
            search_term = vim.vars['notmuch_folders'][vc.window.cursor[0]-1][1].decode()
            return [search_term]
        msg_id = get_msg_id()
        if msg_id == '':
            return
        DBASE.open(PATH)
        msg = DBASE.find_message(msg_id)
        if msg is None:  # メール・ファイルが全て削除されている場合
            return
        if f_type != 'notmuch-edit':
            search_term = b_v['search_term'].decode()
        # msg = DBASE.find_message(msg_id)
        # if msg is None:  # メール・ファイルが全て削除されている場合
        #     return
        if f_type == 'notmuch-edit':
            lists = []
        elif bnum == vim.bindeval('s:buf_num')['thread'] \
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
        if f_type != 'notmuch-edit':
            pgp_result = b_v['pgp_result'].decode()
            if pgp_result != '':
                lists.append('PGP result : ' + pgp_result.split('\n')[0])
                for ls in pgp_result.split('\n')[1:]:
                    if ls != '':
                        lists.append('             ' + ls)
        return lists

    info = get_mail_info()
    if info is None:
        return
    if vim.bindeval('has("popupwin")'):
        vim_ls = '["'
        for ls in info:
            vim_ls += ls.replace('\\', '\\\\').replace('"', '\\"') + '","'
        vim_ls = vim_ls[:-2] + ']'
        vim.command('call popup_atcursor(' + vim_ls +
                    ',{' +
                    '"border": [1,1,1,1],' +
                    '"drag": 1,' +
                    '"close": "click",' +
                    '"moved": "any",' +
                    '"filter": function("s:close_popup"),' +
                    '"col": 0,' +
                    '"mapping": 0' +
                    '})')
        # '"minwidth": 400,' +
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
    filename = find_mail_file('(' + search_term + ') id:"' + msg_id + '"')
    if filename == '':
        message = 'Already Delete/Move/Change folder/tag'
        filename = find_mail_file('id:"' + msg_id + '"')
    if filename == '':
        message = 'Not found file.'
    else:
        # 開く前に呼び出し元となるバッファ変数保存
        b_v = vim.current.buffer.vars['notmuch']
        subject = b_v['subject']
        date = b_v['date']
        msg_id = b_v['msg_id']
        tags = b_v['tags']
        with open(filename, 'rb') as fp:
            msg_file = email.message_from_binary_file(fp)
        for part in msg_file.walk():  # 最初の Content-Type: text/xxxx を探す
            if part.is_multipart():
                continue
            if part.get_content_disposition() == 'attachment':  # 先に判定しないと、テキストや HTML ファイルが本文扱いになる
                if part.get_content_type().find('application/pgp-encrypted') == 0 \
                        or part.get_content_type().find('application/x-pkcs7-mime') == 0\
                        or part.get_content_type().find('application/pkcs7-mime') == 0:
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
        b_v['notmuch'] = {}
        b_v = b_v['notmuch']
        b_v['subject'] = subject
        b_v['date'] = date
        b_v['msg_id'] = msg_id
        b_v['tags'] = tags
        vim.command('call s:augroup_notmuch_select(' + active_win + ', 1)')
        if MAILBOX_TYPE == 'Maildir':
            draft_dir = PATH + os.sep + '.draft'
        else:
            draft_dir = PATH + os.sep + 'draft'
        if filename.startswith(draft_dir + os.sep) or 'draft' in tags.decode().split(' '):
            vim.command('setlocal filetype=notmuch-draft noswapfile')
            vim.command('call s:au_write_draft()')
        else:
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


def send_mail(filename):  # ファイルをメールとして送信←元のファイルは削除
    # 添付ファイルのエンコードなどの変換済みデータを送信済み保存
    if VIM_MODULE:
        for b in vim.buffers:
            if b.name == filename:  # Vim で開いている
                if b.options['modified'] or b.options['bufhidden'] != b'':
                    # 更新もしくは隠れバッファ等でもない普通に開いているバッファなので送信しない
                    return
    with open(filename, 'r') as fp:
        msg_data = fp.read()
        # msg_file = email.message_from_file(fp) を用いるとヘッダがエンコードされる+不正なヘッダ書式をチェック出来ない
    msg_id = []
    if send_str(msg_data, msg_id):
        os.remove(filename)


def send_vim_buffer():
    msg_data = '\n'.join(vim.current.buffer[:])
    msg_id = []
    if send_str(msg_data, msg_id):
        if len(msg_id):  # タグの反映
            marge_tag(msg_id[0], True)
        if vim.bindeval('len(getbufinfo())') == 1:  # 送信用バッファのみ
            vim.command('cquit')
        f = vim.current.buffer.name
        vim.command('bwipeout!')
        if MAILBOX_TYPE == 'Maildir':
            f = re.sub('[DFPRST]+$', '', f) + '*'
        rm_file_core(f)


def marge_tag(msg_id, send):   # 下書きバッファと notmuch databae のタグをマージ
    # send 送信時か?→draft, unread タグは削除
    b = vim.current.buffer
    DBASE.open(PATH)
    msg = change_tags_before(msg_id)
    if msg is None:
        DBASE.close()
    else:
        b_v = b.vars['notmuch']
        b_tag = b_v['tags'].decode().split(' ')
        if send:
            if 'draft' in b_tag:
                b_tag.remove('draft')
            if 'unread' in b_tag:
                b_tag.remove('unread')
            del_tag = ['draft', 'unread']
        else:
            del_tag = []
        add_tag = []
        m_tag = []
        for t in msg.get_tags():
            m_tag.append(t)
        for t in m_tag:
            if not (t in b_tag):
                del_tag.append(t)
        delete_msg_tags(msg, del_tag)
        for t in b_tag:
            if not (t in m_tag):
                add_tag.append(t)
        add_msg_tags(msg, add_tag)
        change_tags_after(msg, False)


def send_str(msg_data, msgid):  # 文字列をメールとして保存し設定従い送信済みに保存
    from email.mime.multipart import MIMEMultipart
    from email.mime.base import MIMEBase
    from email.message import EmailMessage
    import mimetypes                    # ファイルの MIMETYPE を調べる
    # ATTACH = 0x01
    PGP_ENCRYPT = 0x10
    PGP_SIGNATURE = 0x20
    PGPMIME_ENCRYPT = 0x100
    PGPMIME_SIGNATURE = 0x200
    SMIME_ENCRYPT = 0x1000
    SMIME_SIGNATURE = 0x2000
    # MIME_ON = PGPMIME_ENCRYPT | PGPMIME_SIGNATURE | SMIME_ENCRYPT | SMIME_SIGNATURE
    ALL_ENCRYPT = SMIME_ENCRYPT | PGP_ENCRYPT | PGPMIME_ENCRYPT
    ALL_SIGNATURE = SMIME_SIGNATURE | PGP_SIGNATURE | PGPMIME_SIGNATURE
    # ALL_FLAG = ALL_ENCRYPT | ALL_SIGNATURE

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
        def attach_binary(path, main, subtype, name_param, file_param):
            with open(path, 'rb') as fp:
                part = MIMEBase(maintype, subtype, **name_param)
                part.set_payload(fp.read())
                email.encoders.encode_base64(part)
            return part

        if path == '':
            return True
        path = os.path.expandvars(os.path.expanduser(path))
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
            try:
                with open(path, 'r') as fp:
                    part = MIMEText(fp.read(), _subtype=subtype)
            except UnicodeDecodeError:  # utf-8 以外の text ファイルで失敗するケースがある
                part = attach_binary(path, maintype, subtype, name_param, file_param)
        else:
            part = attach_binary(path, maintype, subtype, name_param, file_param)
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

    def encrypt(s, header):
        def add_only(header):
            adr = ''
            for s in ['to', 'from', 'cc', 'bcc']:
                if s in header:
                    adr = adr + ',' + header[s]
            ls = []
            for i in address2ls(adr):
                ls.append(email2only_address(i).lower())
            return list(set(ls))

        h = {}
        for k, i in header.items():
            h[k.lower()] = i
        if flag & SMIME_ENCRYPT:
            cmd = ['gpgsm', '--encrypt', '--base64', '--output', '-']
        else:
            if flag & PGP_SIGNATURE:
                local_user = email2only_address(h['from'])
                cmd = ['gpg', '--sign', '--local-user', local_user, '--encrypt', '--armor', '--output', '-']
            else:
                cmd = ['gpg', '--encrypt', '--armor', '--output', '-']
        if shutil.which(cmd[0]) is None:
            return False, s
        for i in add_only(h):
            cmd.append('--recipient')
            cmd.append(i)
        body_tmp = TEMP_DIR + 'body.tmp'
        # with open(body_tmp, 'w', encoding=charset, newline="\r\n") as fp:
        #     fp.write(s)  # UTF-8 以外が保存できるようにエンコードを指定し、改行コードを CR+LF に統一して保存
        with open(body_tmp, 'w', encoding=charset) as fp:
            fp.write(s)  # UTF-8 以外が保存できるようにエンコードを指定して保存
        cmd.append(body_tmp)
        ret = run(cmd, stdout=PIPE, stderr=PIPE, text=True)
        # ret = run([cmd, '--decrypt'], input=decrypt, stdout=PIPE, stderr=PIPE)
        rm_file_core(body_tmp)
        if ret.returncode:
            print_warring(ret.stderr)
            return False, s
        return True,  ret.stdout

    def signature(s, header):
        h = {}
        for k, i in header.items():
            h[k.lower()] = i
        local_user = email2only_address(h['from'])
        if flag & SMIME_SIGNATURE:
            cmd = ['gpgsm', '--detach-sign', '--local-user', local_user, '--base64',
                   '--output', '-']
        elif flag & PGPMIME_SIGNATURE:
            cmd = ['gpg', '--detach-sign', '--local-user', local_user, '--armo',
                   '--output', '-']
        elif flag & PGP_SIGNATURE:
            s += '\n'  # 末尾の改行が削除されているので追加
            cmd = ['gpg', '--clearsign', '--local-user', local_user,
                   '--output', '-']
        else:
            print_warring('Programing Error')
            return False
        if shutil.which(cmd[0]) is None:
            return False, s
        body_tmp = TEMP_DIR + 'body.tmp'
        with open(body_tmp, 'w', encoding=charset,  # UTF-8 以外が保存できるようにエンコードを指定
                  newline="\r\n") as fp:  # 署名用に改行コード CR+LF 指定
            fp.write(s)
        cmd.append(body_tmp)
        ret = run(cmd, stdout=PIPE, stderr=PIPE, text=True)
        if ret.returncode:
            print_warring(ret.stderr)
            return False, s
        rm_file_core(body_tmp)
        return True, ret.stdout

    def get_header_ls():  # ヘッダ文字列情報をリストに変換
        def get_flag(search):  # ヘッダー部分に search があるか?
            return re.search(search, h_item, re.IGNORECASE) is not None

        h_data = {}
        pre_h = ''
        attach = []
        flag = 0
        for h in headers.split('\n'):
            match = re.match(r'^[A-Za-z-]+:\s*', h)
            if match is None:
                match = re.match(r'^\s+', h)
                if match is None:
                    print_error('Illegal header:' + h)
                    return None, None, None
                h_data[pre_h] += h[match.end():]
            else:
                h_term = h[:h.find(':')]
                h_item = h[match.end():]
                if h_item != '':
                    h_term_l = h_term.lower()
                    if h_term_l == 'attach':
                        attach.append(h_item)
                    elif h_term_l == 'encrypt':
                        flag_check = (get_flag(r'\bS[/-]?MIME\b') * SMIME_ENCRYPT) \
                             | (get_flag(r'\bPGP\b') * PGP_ENCRYPT) \
                             | (get_flag(r'\bPGP[/-]?MIME\b') * PGPMIME_ENCRYPT)
                        if not flag_check:
                            print_error('The encryption method is wrong.')
                            return None, None, None
                        flag |= flag_check
                    elif h_term_l == 'signature':
                        flag_check = (get_flag(r'\bS[/-]?MIME\b') * SMIME_SIGNATURE) \
                             | (get_flag(r'\bPGP\b') * PGP_SIGNATURE) \
                             | (get_flag(r'\bPGP[/-]?MIME\b') * PGPMIME_SIGNATURE)
                        if not flag_check:
                            print_error('The signature method is wrong.')
                            return None, None, None
                        flag |= flag_check
                    else:
                        h_data[h_term] = h_item
                pre_h = h_term
        # 暗号化・署名が複数指定されていた時、暗号化と署名方法に矛盾していた時のために flag を指定し直す
        if flag & SMIME_ENCRYPT:
            flag = SMIME_ENCRYPT | (SMIME_SIGNATURE if flag & ALL_SIGNATURE else 0x0)
        elif flag & PGPMIME_ENCRYPT:
            flag = PGPMIME_ENCRYPT | (PGPMIME_SIGNATURE if flag & ALL_SIGNATURE else 0x0)
        elif flag & PGP_ENCRYPT:
            flag = PGP_ENCRYPT | (PGP_SIGNATURE if flag & ALL_SIGNATURE else 0x0)
        elif flag & SMIME_SIGNATURE:
            flag = SMIME_SIGNATURE
        elif flag & PGPMIME_SIGNATURE:
            flag = PGPMIME_SIGNATURE
        elif flag & PGP_SIGNATURE:
            flag = PGP_SIGNATURE
        return h_data, attach, flag

    if shutil.which(SEND_PARAM[0]) is None:
        sys.stderr.write('\'' + SEND_PARAM[0] + '\' is not executable.')
        return False
    # ヘッダ・本文の分離
    match = re.search(r'\n\n', msg_data)
    if match is None:
        headers = msg_data
        mail_context = ''
    else:
        headers = msg_data[:match.start()]
        mail_context = re.sub(r'\n+$', '', msg_data[match.end():])  # ファイル末尾の連続する改行は一旦全て削除
        mail_context = re.sub(r'^\n+', '', mail_context) + '\n'  # 本文最初の改行は全て削除し、最後に改行追加
    header_data, attachments, flag = get_header_ls()
    if ('utf-8' in SENT_CHARSET):  # utf-8+8bit を可能にする 無いとutf-8+base64
        email.charset.add_charset(
            'utf-8', email.charset.SHORTEST, None, 'utf-8')
    for charset in SENT_CHARSET:  # 可能な charset の判定
        try:
            mail_body = mail_context.encode(charset)
            break
        except UnicodeEncodeError:
            pass
    else:
        charset = 'utf-8'
        mail_body = mail_context.encode('utf-8')
    if flag is None:
        return False
    if flag & PGP_ENCRYPT:
        ret, mail_body = encrypt(mail_context, header_data)
        if not ret:
            return False
        mail_body = MIMEText(mail_body, 'plain', charset)
    elif flag & PGP_SIGNATURE:
        msg = EmailMessage()
        if charset == 'us-ascii' or charset == 'ascii':
            t_encoding = '7bit'
        # elif charset == 'utf-8': utf-8 でも PGP 署名では quoted-printable
        #     t_encoding = 'base64'
        else:
            t_encoding = 'quoted-printable'
        msg.set_content(mail_context, cte=t_encoding, charset=charset)
        mail_context = msg.get_payload()
        ret, mail_context = signature(mail_context, header_data)
        if not ret:
            return False
        mail_body = MIMEText(mail_context, 'plain', charset)
        mail_body.replace_header('Content-Transfer-Encoding', t_encoding)
    else:
        if (flag & ALL_SIGNATURE) and not (flag & ALL_ENCRYPT):  # 暗号化なしの署名付きは quoted-printable か base64 使用
            mail_body = EmailMessage()
            if charset == 'us-ascii' or charset == 'ascii':
                t_encoding = '7bit'
            elif charset == 'utf-8':
                t_encoding = 'base64'
            else:
                t_encoding = 'quoted-printable'
            mail_body.set_content(mail_context, cte=t_encoding, charset=charset)
        else:
            mail_body = MIMEText(mail_body, 'plain', charset)
    if len(attachments) != 0:
        msg_send = MIMEMultipart()
        msg_send.attach(mail_body)
    else:
        msg_send = mail_body
    for attachment in attachments:  # 添付ファイル追加
        if not attach_file(msg_send, attachment):
            return False
    if (flag & SMIME_SIGNATURE):  # PGP/MIME 電子署名
        msg0 = msg_send
        ret, sig = signature(msg0.as_string(), header_data)
        if not ret:
            return False
        msg1 = EmailMessage()
        msg1['Content-Type'] = 'application/pkcs7-signature; name="smime.p7s"'
        msg1['Content-Transfer-Encoding'] = 'base64'
        msg1['Content-Disposition: attachment'] = 'filename="smime.p7s"'
        msg1['Content-Description'] = 'S/MIME Cryptographic Signature'
        msg1.set_payload(sig)
        msg_send = MIMEMultipart(_subtype="signed", micalg="sha-256", protocol="application/pkcs7-signature")
        msg_send.attach(msg0)
        msg_send.attach(msg1)
    elif (flag & PGPMIME_SIGNATURE):  # PGP/MIME 電子署名
        msg0 = msg_send
        ret, sig = signature(msg0.as_string(), header_data)
        if not ret:
            return False
        msg1 = EmailMessage()
        msg1['Content-Type'] = 'application/pgp-signature; name="signature.asc"'
        msg1['Content-Description'] = 'OpenPGP digital signature'
        msg1.set_payload(sig)
        msg_send = MIMEMultipart(_subtype="signed", micalg="pgp-sha1", protocol="application/pgp-signature")
        msg_send.attach(msg0)
        msg_send.attach(msg1)
    if (flag & SMIME_ENCRYPT):  # S/MIME 暗号化
        if SMIME_SIGNATURE:  # 改行コードを CR+LF に統一して渡す
            ret, mail_body = encrypt(re.sub(r'(\r\n|\n\r|\n|\r)', r'\r\n',
                                            msg_send.as_string()), header_data)
        else:
            ret, mail_body = encrypt(msg_send.as_string(), header_data)
        if not ret:
            return False
        msg_send = MIMEBase(_maintype="application", _subtype="pkcs7-mime",
                            name="smime.p7m", smime_type="enveloped-data")
        # msg_send = MIMEBase(_maintype="application", _subtype="pkcs7-mime", name="smime.p7m")
        # msg_send.replace_header(_name="Content-Type",
        #     _value='application/pkcs7-mime; name="smime.p7m"; smime-type=enveloped-data')
        msg_send.add_header(_name="Content-Transfer-Encoding", _value="base64")
        msg_send.add_header(_name="Content-Disposition", _value="attachment", filename="smime.p7m")
        msg_send.add_header(_name="Content-Description", _value="S/MIME Encrypted Message")
        msg_send.set_payload(mail_body)
    elif (flag & PGPMIME_ENCRYPT):  # PGP/MIME 暗号化
        msg0 = EmailMessage()
        msg0.add_header(_name="Content-Type", _value="application/pgp-encrypted")
        msg0.add_header(_name="Content-Description", _value="PGP/MIME version identification")
        msg0.set_payload("Version: 1" + "\n")
        ret, mail_body = encrypt(msg_send.as_string(), header_data)
        if not ret:
            return False
        msg = EmailMessage()
        msg.add_header(_name="Content-Type", _value="application/octet-stream", name="encrypted.asc")
        msg.add_header(_name="Content-Description", _value="OpenPGP encrypted message")
        msg.add_header(_name="Content-Disposition", _value="inline", filename="encrypted.asc")
        msg.set_payload(mail_body)
        msg_send = MIMEBase(_maintype="multipart", _subtype="encrypted", protocol="application/pgp-encrypted")
        msg_send.attach(msg0)
        msg_send.attach(msg)
    # ヘッダ設定
    msg_data = ''  # 送信済みとして下書きを使う場合に備えたデータ初期化
    send_headers = ['from', 'to', 'cc', 'bcc', 'reply-to',
                    'resent-to', 'resent-cc', 'resent-bcc']
    ignore_msg_data = ['date', 'content-type', 'content-transfer-encoding', 'message-id']
    # ↑下書きを出来る限りそのままで送信済みとして保存する場合でも必ず付け直しをするヘッダ
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
    # 必須ヘッダの追加
    if msg_send.get('Subject') is None:
        msg_send['Subject'] = ''
    if msg_send.get('To') is None and msg_send.get('Cc') is None:
        if msg_send.get('Bcc') is None:
            print_warring('No address')
            return False
        msg_send['To'] = 'undisclosed-recipients: ;'
    # 他からコピーした場合もあり得るので、Message-ID は常に作り直す
    del msg_send['Message-ID']
    msgid_id, msgid_domain = get_user_id(msg_send.get('From'))
    if msgid_id is None:
        msg_id = email.utils.make_msgid()
    else:
        msg_id = email.utils.make_msgid(msgid_id.upper(), msgid_domain.upper())
    msg_send['Message-ID'] = msg_id
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
            msg_data += '\nMessage-ID: ' + msg_id
            if attachments is not None:
                for attachment in attachments:
                    msg_data += '\nX-Attach: ' + attachment
            print(msg_data)
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
    msg_id = msg_id[1:-1]
    msg = DBASE.find_message(msg_id)
    if msg is not None:
        add_tag.append(msg.get_tags())
        add_tag.remove('draft')
        add_tag.remove('unread')
    DBASE.close()
    move_mail_main(msg_id, send_tmp, sent_dir, ['draft', 'unread'], add_tag, True)  # 送信済み保存
    msgid.append(msg_id)
    return True


def send_search(search_term):
    DBASE.open(PATH)
    query = notmuch.Query(DBASE, search_term)
    for msg in query.search_messages():
        files = msg.get_filenames().__str__().split('\n')
        for f in files:
            if os.path.isfile(f):
                send_mail(f)
                break
        else:
            print_warring('Not exist mail file.')
        for f in files:  # 同じ内容のファイルが複数あった時、残りを全て削除
            if os.path.isfile(f):
                rm_file_core(f)
    DBASE.close()
    return


def send_vim():
    b = vim.current.buffer
    bufnr = b.number
    b_v = b.vars['notmuch']
    if b.options['filetype'] == b'notmuch-draft':
        send_vim_buffer()
    else:
        buf_num = vim.bindeval('s:buf_num')
        if bufnr == buf_num['folders']:
            send_search('(folder:draft or folder:.draft or tag:draft) ' +
                        'not tag:sent not tag:Trash not tag:Spam')
        elif 'search_term' in b_v:
            s = b_v['search_term'].decode()
            if bufnr == buf_num['thread'] \
                    or (s in buf_num['search'] and bufnr == buf_num['search'][s]):
                send_search(s +
                            ' ((folder:draft or folder:.draft or tag:draft) ' +
                            'not tag:sent not tag:Trash not tag:Spam)')
            else:  # buf_num['show'] または buf_num['view'][s]
                msg_id = get_msg_id()
                if msg_id == '':
                    return
                send_search('id:' + msg_id +
                            ' ((folder:draft or folder:.draft or tag:draft) ' +
                            'not tag:sent not tag:Trash not tag:Spam)')
    if 'buf_num' in vim.bindeval('s:'):
        reprint_folder2()


def new_mail(s):  # 新規メールの作成 s:mailto プロトコルを想定
    def get_mailto(s, headers):  # mailto プロトコルからパラメータ取得
        from urllib.parse import unquote    # URL の %xx を変換

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
                if notmuch.Query(DBASE, '(' + s + ') and id:"' + msg_id + '"').count_messages():
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
    b.vars['notmuch'] = {}
    b.vars['notmuch']['subject'] = headers['subject']
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

    active_win, msg_id = check_org_mail()
    if not active_win:
        return
    msg_data = get_mail_body(active_win)
    before_make_draft(active_win)
    b = vim.current.buffer
    b.vars['notmuch'] = {}
    b_v = b.vars['notmuch']
    b_v['org_mail_body'] = msg_data
    DBASE.open(PATH)
    msg = DBASE.find_message(msg_id)
    headers = vim.vars['notmuch_draft_header']
    recive_from_name = msg.get_header('From')
    b_v['org_mail_from'] = email2only_name(recive_from_name)
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
            b_v['subject'] = subject
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
    b_v['org_mail_date'] = email.utils.parsedate_to_datetime(
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
    b.vars['notmuch'] = {}
    b_v = b.vars['notmuch']
    cut_line = 70
    for h in ['Cc', 'To', 'Date', 'Subject', 'From']:
        s = msg.get_header(h).replace('\t', ' ')
        if s != '':
            msg_data = h + ': ' + ' ' * (7-len(h)) + s + '\n' + msg_data
        if h == 'Subject':
            subject = 'FWD:' + s
            b_v['subject'] = subject
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
    b_v['org_mail_body'] = msg_data
    b.append('')
    after_make_draft(b)
    vim.command('call s:au_forward_mail()')


def before_make_draft(active_win):  # 下書き作成の前処理
    if vim.current.buffer.options['filetype'].decode()[:8] == 'notmuch-' \
            or vim.bindeval('wordcount()["bytes"]') != 0:
        vim.command(vim.vars['notmuch_open_way']['draft'].decode())
    vim.command('call s:mail_quote()')
    if MAILBOX_TYPE == 'Maildir':
        mbox_type = mailbox.Maildir
        draft_dir = PATH + os.sep + '.draft'
    else:
        mbox_type = mailbox.MH
        draft_dir = PATH + os.sep + 'draft'
    mbox = mbox_type(PATH)
    if not ('draft' in mbox.list_folders()):
        mbox.add_folder('draft')
    mbox = mbox_type(draft_dir)
    f = str(mbox.add(email.message.Message()))
    mbox.remove(f)
    if MAILBOX_TYPE == 'Maildir':
        f = draft_dir + os.sep + 'cur' + os.sep + f + ':2,DS'
    else:
        f = draft_dir + os.sep + f
    vim.current.buffer.name = f
    vim.command('setlocal filetype=notmuch-draft noswapfile')
    vim.command('call s:augroup_notmuch_select(' + active_win + ', 0)')


def after_make_draft(b):
    b.append('')
    del b[0]
    i = 0
    for s in b:
        if s == 'Attach: ':
            break
        i += 1
    now = email.utils.localtime()
    msg_id = email.utils.make_msgid()
    b_v = vim.current.buffer.vars
    b_v = b_v['notmuch']
    b_v['date'] = now.strftime(DATE_FORMAT)
    b_v['msg_id'] = msg_id[1:-1]
    b_v['tags'] = 'draft'
    b.append('Date: ' + email.utils.format_datetime(now), i)
    # Message-ID はなくとも Notmuch は SHA1 を用いたファイルのチェックサムを使って管理できるが tag 追加などをするためには、チェックサムではファイル編集で変わるので不都合
    b.append('Message-ID: ' + msg_id, i + 1)
    b.options['modified'] = 0
    vim.command('call s:au_write_draft()')


def save_draft():  # 下書きバッファと notmuch databae のタグをマージと notmuch-folders の更新
    # 下書き保存時に呼び出される
    notmuch_new(False)
    b = vim.current.buffer
    msg_id = b.vars['notmuch']['msg_id'].decode()
    marge_tag(msg_id, False)
    # Maildir だとフラグの変更でファイル名が変わり得るので、その時はバッファのファイル名を変える
    DBASE.open(PATH)
    m_f = DBASE.find_message(msg_id).get_filename()
    b_f = b.name
    if m_f != b_f:
        b.name = m_f
        vim.command('write! | bwipeout! ' + b_f)
    reprint_folder()
    DBASE.close()


def set_new_after(n):  # 新規メールの From ヘッダの設定や署名の挿入
    if vim.current.window.cursor[0] < len(vim.current.buffer):
        return
    vim.command('autocmd! NotmuchNewAfter' + str(n))
    to, h_from = set_from()
    insert_signature(to, h_from)


def check_org_mail():  # 返信・転送可能か? 今の bufnr() と msg_id を返す
    b = vim.current.buffer
    is_search = b.number
    b_v = b.vars['notmuch']
    b_v['subject'] = ''
    active_win = str(is_search)
    show_win = vim.bindeval('s:buf_num')['show']
    is_search = not(vim.bindeval('s:buf_num')['folders'] == is_search
                    or vim.bindeval('s:buf_num')['thread'] == is_search
                    or show_win == is_search)
    if is_search:
        show_win = \
            vim.bindeval('s:buf_num')["view"][b_v['search_term'].decode()]
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
    if vim.current.window.cursor[0] < len(vim.current.buffer):
        return
    vim.command('autocmd! NotmuchReplyAfter' + str(n))
    to, h_from = set_from()
    b = vim.current.buffer
    b_v = b.vars['notmuch']
    if vim.vars.get('notmuch_signature_prev_quote', 0):
        insert_signature(to, h_from)
    b.append('On ' + b_v['org_mail_date'].decode() + ', ' +
             email2only_name(b_v['org_mail_from'].decode()) + ' wrote:')
    for line in b_v['org_mail_body'].decode().split('\n'):
        b.append('> ' + line)
    b.append('')
    if not vim.vars.get('notmuch_signature_prev_quote', 0):
        insert_signature(to, h_from)
    del b_v['org_mail_date']
    del b_v['org_mail_body']
    del b_v['org_mail_from']


def set_forward_after(n):  # 返信メールの From ヘッダの設定や引用本文・署名の挿入
    if vim.current.window.cursor[0] < len(vim.current.buffer):
        return
    vim.command('autocmd! NotmuchForwardAfter' + str(n))
    to, h_from = set_from()
    b = vim.current.buffer
    if vim.vars.get('notmuch_signature_prev_forward', 0):
        insert_signature(to, h_from)
    for line in b.vars['notmuch']['org_mail_body'].decode().split('\n'):
        b.append(line)
    b.append('')
    if not vim.vars.get('notmuch_signature_prev_forward', 0):
        insert_signature(to, h_from)
    del b.vars['notmuch']['org_mail_body']


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

    def compress_addr():  # 名前+メール・アドレスで両者が同じならメール・アドレスだけに
        def compress_addr_core(s):
            addr = []
            if re.search(r',\s*$', s) is None:
                last = ''
            else:
                last = ','
            for i in address2ls(s):
                n, a = email.utils.parseaddr(i)
                if n == a or n == '':
                    addr.append(a)
                else:
                    addr.append(i)
            return ', '.join(addr) + last

        is_addr = False
        b = vim.current.buffer
        for i, b_i in enumerate(b):
            match = re.match(r'((From|To|Cc|Bcc):|\s)\s*(.+)', b_i, flags=re.IGNORECASE)
            if match is None:
                is_addr = False
                continue
            elif match.group(2) is None and is_addr:
                b[i] = match.group(1) + ' ' + compress_addr_core(match.group(3))
            elif match.group(2) is not None:
                is_addr = True
                b[i] = match.group(1) + ' ' + compress_addr_core(match.group(3))
            elif b_i == '':
                break

    to = []
    h_from = (0, '')
    b = vim.current.buffer
    for i, l in enumerate(b):
        match = re.match(r'(From|To|Cc|Bcc|Subject): *(.*)', l, flags=re.IGNORECASE)
        if match is None:
            continue
        elif match.group(1).lower() == 'subject':
            b.vars['notmuch']['subject'] = match.group(2)
        elif match.group(1).lower() == 'from':
            h_from = (i, match.group(2))
        else:
            g = match.group(2)
            if g != '':
                to.append(g)
    if h_from[1] == '':
        h_From = get_user_From(to)
        if re.match(r'From:', b[h_from[0]], flags=re.IGNORECASE) is None:
            b.append('From: ' + h_From, h_from[0])
        else:
            b[h_from[0]] = 'From: ' + h_From
    else:
        h_From = h_from[1]
    to = sorted(set(to), key=to.index)
    compress_addr()
    return to, h_From


def insert_signature(to_name, from_name):  # 署名挿入
    def get_signature(from_to):  # get signature filename
        if from_to == '':
            return ''
        if 'notmuch_signature' in vim.vars:
            sigs = vim.vars['notmuch_signature']
            from_to = email2only_address(from_to)
            sig = sigs.get(from_to, sigs.get('*', b'$HOME/.signature'))
            sig = os.path.expandvars(os.path.expanduser(sig.decode()))
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
    if args is None:  # 複数選択してフォルダを指定しなかった時の 2 つ目以降
        return
    mbox = args[2:]
    if opened_mail(False):
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
            move_mail_main(msg_id, f, mbox, [], tags, False)
        else:
            print('Already Delte: ' + f)
    DBASE.close()
    # if 'folders' in vim.bindeval('s:buf_num'):
    reprint_folder2()  # 閉じた後でないと、メール・ファイル移動の情報がデータベースに更新されていないので、エラーになる
    return [1, 1, mbox]  # Notmuch mark-command (command_marked) から呼び出された時の為、リストで返す


def move_mail_main(msg_id, path, move_mbox, delete_tag, add_tag, draft):  # メール移動
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
    if VIM_MODULE and opened_mail(draft):
        print_warring('Can not update Notmuch database.\nPlease save and close mail.')
        return
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
    if opened_mail(False):
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
            return [], '', 0
    DBASE.open(PATH)
    msg = DBASE.find_message(msg_id)
    if msg is None:  # すでにファイルが削除されているとき
        print('The email has already been completely deleted.')
        DBASE.close()
        return [], '', 0
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


def is_draft():
    b = vim.current.buffer
    if b.options['filetype'] == b'notmuch-draft':
        if MAILBOX_TYPE == 'Maildir':
            draft_dir = PATH + os.sep + '.draft'
        else:
            draft_dir = PATH + os.sep + 'draft'
        if b.name.startswith(draft_dir + os.sep) \
                or 'draft' in b.vars['notmuch']['tags'].decode().split(' '):
            return True
    return False


def do_mail(cmd, args):  # mail に対しての処理、folders では警告表示
    # 行番号などのコマンド引数
    b = vim.current.buffer
    bnum = b.number
    b_v = b.vars['notmuch']
    if is_draft():
        args = cmd(b_v['msg_id'].decode(), '', args)
        return
    try:
        search_term = b_v['search_term'].decode()
    except KeyError:
        print_warring('Don\'t open mail or is done with \'folders\'.')
        return
    if search_term == '':
        print_warring('Don\'t open mail or is done with \'folders\'.')
        return
    if bnum == vim.bindeval('s:buf_num')['thread'] \
        or ((search_term in vim.bindeval('s:buf_num')['search'])
            and bnum == vim.bindeval('s:buf_num')['search'][search_term]):
        args[0] = int(args[0])
        args[1] = int(args[1])
        for i in range(args[0], args[1]+1):
            msg_id = THREAD_LISTS[search_term]['list'][i-1].get_message_id()
            args = cmd(msg_id, search_term, args)
    elif (('show' in vim.bindeval('s:buf_num'))
            and bnum == vim.bindeval('s:buf_num')['show']) \
        or ((search_term in vim.bindeval('s:buf_num')['view'])
            and bnum == vim.bindeval('s:buf_num')['view'][search_term]):
        args = cmd(b_v['msg_id'].decode(), search_term, args)


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
        'thread-sort',
        'thread-toggle',
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
        search_term = b.vars['notmuch']['search_term'].decode()
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
            msg_id = THREAD_LISTS[search_term]['list'][line].get_message_id()
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
    # DBASE.open(PATH)
    # if 'folders' in vim.bindeval('s:buf_num'):
    reprint_folder2()
    # DBASE.close()


def notmuch_search(search_term):
    i_search_term = ''
    search_term = search_term[2:]
    if search_term == '' or search_term == []:  # コマンド空
        if vim.current.buffer.number == vim.bindeval('s:buf_num')['folders']:
            i_search_term = vim.vars['notmuch_folders'][vim.current.window.cursor[0]-1][1].decode()
        else:
            i_search_term = vim.current.buffer.vars['notmuch']['search_term'].decode()
        search_term = vim.eval(
            'input("search term: ", "' + i_search_term + '", "customlist,Complete_search_input")')
        if search_term == '':
            return
    elif type(search_term) == list:
        search_term = ' '.join(search_term)
    if not check_search_term(search_term):
        return
    DBASE.open(PATH)
    if search_term == i_search_term:
        if vim.current.buffer.number == vim.bindeval('s:buf_num')['folders']:
            if search_term == \
                    vim.buffers[vim.bindeval('s:buf_num')['thread']].vars['notmuch']['search_term'].decode():
                vim.command('call win_gotoid(bufwinid(s:buf_num["thread"]))')
            else:
                open_thread(vim.current.window.cursor[0], True, False)
                if is_same_tabpage('show', ''):
                    open_mail(search_term,
                              vim.windows[vim.bindeval('s:buf_num')['thread']].cursor[0] - 1,
                              str(vim.buffers[vim.bindeval('s:buf_num')['thread']].number))
        return
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
    notmuch_search([0, 0, search_term])  # 先頭2つの0はダミーデータ
    vim.command('normal! zO')
    index = [i for i, msg in enumerate(
        THREAD_LISTS[search_term]['list']) if msg.get_message_id() == msg_id]
    vim.current.window.cursor = (index[0]+1, 0)


def check_search_term(s):
    if s == '*':
        print_warring('Error: When you want to search all mail, use \'path:**\'.')
        return False
    elif len(re.sub(r'[^"]', '', s.replace(r'\\', '').replace(r'\"', ''))) % 2:
        print_warring('Error: \'"\' (double quotes) is not pared.')
        return False
    bra = len(re.sub(r'[^(]', '', s.replace(r'\\', '').replace(r'\(', '')))
    cket = len(re.sub(r'[^)]', '', s.replace(r'\\', '').replace(r'\)', '')))
    if bra != cket:
        print_warring('Error: \'()\', round bracket is not pared.')
        return False
    return True


GLOBALS = globals()

initialize()
if not VIM_MODULE:
    SEND_PARAM = ['msmtp', '-t', '-a', 'Nifty', '-X', '-']
    send_search('(folder:draft or folder:.draft or tag:draft) ' +
                'not tag:sent not tag:Trash not tag:Spam')
    # import time
    # s = time.time()
    # # print_thread_view('tag:inbox not tag:Trash and not tag:Spam')
    # # print_thread_view('path:**')
    # DBASE.open(PATH)
    # make_thread_core('path:**')
    # DBASE.close()
    # print(time.time() - s)
