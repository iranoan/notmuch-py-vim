#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# vim:fileencoding=utf-8 fileformat=unix
#
# Author:  Iranoan <iranoan+vim@gmail.com>
# License: GPL Ver.3.

import codecs
import copy
import datetime                   # 日付
import email
import glob                       # ワイルドカード展開
import locale
import mailbox
import mimetypes                  # ファイルの MIMETYPE を調べる
import os                         # ディレクトリの存在確認、作成
import re                         # 正規表現
import shutil                     # ファイル移動
import sys
from base64 import b64decode
from math import ceil
# from concurrent.futures import ProcessPoolExecutor
# from concurrent.futures import ThreadPoolExecutor
from email.message import Message
from email.mime.base import MIMEBase
from hashlib import sha256        # ハッシュ
from html.parser import HTMLParser
from operator import attrgetter   # ソート
# from operator import itemgetter, attrgetter  # ソート
from quopri import decodestring
from subprocess import PIPE, Popen, TimeoutExpired, run
from urllib.parse import unquote  # URL の %xx を変換

from html2text import HTML2Text   # HTML メールの整形
import notmuch2                   # API で出来ないことは notmuch コマンド (subprocess)
import vim


# vim funtion
vim_has = vim.Function('has')
vim_browse = vim.Function('browse')
vim_getbufinfo = vim.Function('getbufinfo')
vim_win_gotoid = vim.Function('win_gotoid')
vim_bufwinid = vim.Function('bufwinid')
vim_tabpagebuflist = vim.Function('tabpagebuflist')
vim_confirm = vim.Function('confirm')
vim_foldlevel = vim.Function('foldlevel')
vim_popup_atcursor = vim.Function('popup_atcursor')
win_id2tabwin = vim.Function('win_id2tabwin')
vim_winwidth = vim.Function('winwidth')
bufwinnr = vim.Function('bufwinnr')
sign_unplace = vim.Function('sign_unplace')
vim_strdisplaywidth = vim.Function('strdisplaywidth')
vim_win_execute = vim.Function('win_execute')
vim_win_getid = vim.Function('win_getid')


def vim_input(p, *s):
    if not s:
        return vim.Function('input')(p).decode()
    elif len(s) == 2:
        return vim.Function('input')(p, s[0], s[1]).decode()
    return vim.Function('input')(p, s[0]).decode()


def vim_input_ls(p, s, comp):
    return vim_input(p, s, comp).split()


def vim_goto_bufwinid(n):
    return vim_win_gotoid(vim_bufwinid(n))
    # return vim.bindeval('win_gotoid(bufwinid(' + str(n) + '))')  # 予備として記述を残しておく


def vim_win_id2tabwin(k, s):
    return (win_id2tabwin(vim_bufwinid(s_buf_num(k, s))))[0]


def vim_bufwinnr(k):
    return bufwinnr(s_buf_num(k, ''))


def vim_sign_unplace(n):
    return sign_unplace('mark_thread', {'name': 'notmuch', 'buffer': n})


def s_buf_num_dic():
    # try:
    #     return vim.bindeval('buf_num')
    # except vim.error:
    #     return vim.bindeval('s:buf_num')
    return vim.bindeval('buf_num')


def script_root():
    # try:
    #     return vim.bindeval('script_root').decode()
    # except vim.error:
    #     return vim.bindeval('s:script_root').decode()
    return vim.bindeval('script_root').decode()


def s_buf_num(k, s):
    if k not in s_buf_num_dic():
        return 0
    if s != '':
        return s_buf_num_dic()[k][s]
    return s_buf_num_dic()[k]


def is_gtk():
    if vim_has('gui_running') \
            and re.match(r'\<with GTK\d\? GUI\.', vim.eval('execute("version")')) != -1:
        return 1
    return 0


def print_warring(msg):
    """ display Warning."""
    msg = msg.replace('"', '\\"').replace('\n', '" | echomsg "')
    vim.command('redraw | echohl WarningMsg | echomsg "' + msg + '" | echohl None')


def print_err(msg):
    """ display Error and exit."""
    msg = msg.replace('"', '\\"').replace('\n', '" | echomsg "')
    vim.command('echohl ErrorMsg | echomsg "' + msg + '" | echohl None')


def print_error(msg):
    """ display Error."""
    vim.command('echohl ErrorMsg | echomsg "' + msg.replace('"', '\\"') + '" | echohl None')


def email2only_name(mail_address):
    """ ヘッダの「名前+アドレス」を名前だけにする """
    name, addr = email.utils.parseaddr(mail_address)
    if name == '':
        return mail_address
    return name


def email2only_address(mail_address):
    """ ヘッダの「名前+アドレス」をアドレスだけにする """
    return email.utils.parseaddr(mail_address)[1]


def str_just_length(string, length):
    '''
    全角/半角どちらも桁数ではなくで幅に揃える (足りなければ空白を埋める)
    →http://nemupm.hatenablog.com/entry/2015/11/25/202936 参考
    '''
    count_widht = vim_strdisplaywidth(string)
    if count_widht == length:
        return string
    elif count_widht > length:
        while True:
            string = string[:-ceil((count_widht - length) / 2)]  # 末尾の多い分を削除
            # ただし全角の場合が有るので、2で割り切り上げ
            count_widht = vim_strdisplaywidth(string)
            if length >= count_widht:
                break
    return string + ' ' * (length - count_widht)


def open_email_file_from_msg(msg):
    '''
    msg: notmuch2.Message
    return email.Message
    * msg.path だとメール・ファイル削除後データベースが削除されている時に対応できないので、候補の全てで存在確認する
    '''
    for f in msg.filenames():
        if os.path.isfile(f):
            return open_email_file(f)
    return None


def open_email_file(f):
    '''
    f: file
    return email.Message
    '''
    try:
        with open(f, 'r') as fp:
            return email.message_from_file(fp)
    except UnicodeDecodeError:
        # ↑普段は上のテキスト・ファイルとして開く
        # 理由は↓だと、本文が UTF-8 そのままのファイルだと、BASE64 エンコードされた状態になり署名検証に失敗する
        with open(f, 'rb') as fp:
            return email.message_from_binary_file(fp)


def get_msg_header(msg, h):
    '''
    msg: email.Message
    h:   header key (name)
    return header item
    '''
    h_cont = msg.get_all(h)
    if h_cont is None:
        return ''
    else:
        data = ''
        for d in h_cont:
            data += d
        return RE_TAB2SPACE.sub(' ', decode_header(data, False, msg.get_content_charset()))


class MailData:  # メール毎の各種データ
    def __init__(self, msg, thread, order, depth):
        def only_address(s):
            adr = []
            for a in email.utils.getaddresses([s]):
                adr.append(a[1])
            return adr

        self._date = msg.date              # 日付 (time_t)
        self._oldest = thread.first        # 同一スレッド中で最も古い日付 (time_t)
        self._latest = thread.last         # 同一スレッド中で最も新しい日付 (time_t)
        self._thread_id = thread.threadid  # スレッド ID
        self._thread_order = order         # 同一スレッド中の表示順
        self.__thread_depth = depth        # 同一スレッド中での深さ
        self._msg_id = msg.messageid       # Message-ID
        self._tags = list(msg.tags)
        # self.__subject = msg.header('Subject') # ←元のメール・ファイルのヘッダの途中で改行されていると最初の行しか取得しない
        # ↑の問題に対応する→スレッド生成でマルチ・スレッドが使えなくなる
        msg_f = open_email_file_from_msg(msg)
        if msg_f is None:
            return None
        self.__subject = get_msg_header(msg_f, 'Subject')
        # 整形した日付
        self.__reformed_date = RE_TAB2SPACE.sub(
            ' ', datetime.datetime.fromtimestamp(self._date).strftime(DATE_FORMAT))
        # 整形した Subject
        self.reform_subject(self.__subject)
        # 整形した宛名
        m_from = get_msg_header(msg_f, 'From')
        m_to = get_msg_header(msg_f, 'To')
        m_to_adr = only_address(m_to)
        if m_to_adr == ['']:
            m_to = get_msg_header(msg_f, 'Cc')
            m_to_adr = only_address(m_to)
            if m_to_adr == ['']:
                m_to = get_msg_header(msg_f, 'Bcc')
                m_to_adr = only_address(m_to)
                if m_to_adr == ['']:
                    m_to = m_from
                    m_to_adr = only_address(m_to)
        # ↓From, To が同一なら From←名前が入っている可能性がより高い
        m_from_name = email2only_name(m_from)
        self._from = m_from_name.lower()
        if m_to_adr == [email2only_address(m_from)]:
            name = RE_TAB2SPACE.sub(' ', m_from_name)
        else:  # それ以外は送信メールなら To だけにしたいので、リスト利用
            self._tags = list(msg.tags)
            # 実際の判定 (To と Reply-To が同じなら ML だろうから除外)
            if (SENT_TAG in self._tags or 'draft' in self._tags) \
                    and (m_to_adr != [email2only_address(get_msg_header(msg_f, 'Reply-To'))]
                         or get_msg_header(msg_f, 'Reply-To') == ''):
                name = []
                for a in email.utils.getaddresses([m_to]):
                    if a[0] != '':
                        name.append(a[0])
                    else:
                        name.append(a[1])
                name = 'To:' + ','.join(name)
            else:
                name = RE_TAB2SPACE.sub(' ', m_from_name)
        self.__reformed_name = name
        string = thread.authors
        # 同一スレッド中のメール作成者 (初期化時はダミーの空文字)
        if string is None:
            self._authors = ''
        else:
            self._authors = ','.join(sorted([RE_TOP_SPACE.sub('', s)
                                     for s in re.split('[,|]', string.lower())]))
            # ↑おそらく | で区切られているのは、使用している search_term では含まれれないが、同じ thread_id に含まれているメールの作成者
        # スレッド・トップの Subject
        string = get_msg_header(open_email_file_from_msg(next(thread.toplevel())), 'Subject')
        self._thread_subject = RE_TAB2SPACE.sub(' ', RE_END_SPACE.sub('', RE_SUBJECT.sub('', string)))
        # 以下はどれもファイルを DBASE.close() で使えなくなる
        # self.__msg = msg                               # msg_p
        # self.__thread = thread                         # thread_p
        # self.__path = msg.filenames()

    def __del__(self):  # デストラクタ←本当に必要か不明
        del self

    def reform_subject(self, s):
        s = RE_TOP_SPACE.sub(
            '', RE_END_SPACE.sub('', RE_SUBJECT.sub('', s.translate(ZEN2HAN))))
        if s == '':  # Subject が空の時そのままだと通常の空白で埋められ、親スレッドが無いと別のスレッド扱いになる
            self._reformed_subject = ' '
        else:
            self._reformed_subject = s

    def get_list(self, flag_thread):
        ls = ''
        tags = self._tags
        for t, emoji in {'unread': '📩', 'draft': '📝', 'flagged': '⭐',
                         'Trash': '🗑', 'attachment': '📎'}.items():
            if t in tags:
                ls += emoji
        ls = ls[:3]
        # ↑基本的には unread, draft の両方が付くことはないので最大3つの絵文字
        emoji_length = 6 - vim_strdisplaywidth(ls)
        if emoji_length:
            emoji_length = '{:' + str(emoji_length) + 's}'
            ls += emoji_length.format('')
        subject = str_just_length(self.__thread_depth * flag_thread * ('  ')
                                  + '  ' + self._reformed_subject, SUBJECT_LENGTH)
        adr = str_just_length(RE_TAB2SPACE.sub(' ', self.__reformed_name), FROM_LENGTH)
        date = RE_TAB2SPACE.sub(' ', self.__reformed_date)
        return RE_END_SPACE.sub('', DISPLAY_FORMAT.format(ls, subject, adr, date))

    def get_folded_list(self):
        date = self.__reformed_date
        subject = str_just_length((self.__thread_depth) * ('  ') + '+ ' + self._reformed_subject,
                                  SUBJECT_LENGTH)
        adr = str_just_length(RE_TAB2SPACE.sub(' ', self.__reformed_name), FROM_LENGTH)
        return RE_END_SPACE.sub('', DISPLAY_FORMAT2.format(subject, adr, date))

    def get_date(self):
        return self.__reformed_date

    def get_subject(self):
        return self.__subject

    def set_subject(self, s):  # 復号化した時、JIS 外漢字が使われデコード結果と異なる時に呼び出され、Subject 情報を書き換える
        self.reform_subject(s)
        self.__subject = s


def make_dump():
    temp_dir = get_temp_dir()
    if vim.vars.get('notmuch_make_dump', 0):
        make_dir(temp_dir)
        ret = run(['notmuch', 'dump', '--gzip', '--output=' + temp_dir + 'notmuch.gz'],
                  stdout=PIPE, stderr=PIPE)
        if ret.returncode:
            print(ret.stderr.decode('utf-8'))
        else:
            shutil.move(temp_dir + 'notmuch.gz', get_save_dir() + 'notmuch.gz')
    rm_file(get_attach_dir())
    rm_file(temp_dir)


def make_dir(dirname):
    if not os.path.isdir(dirname):
        os.makedirs(dirname, 0o700)


def notmuch_new(open_check):
    """ メールを開いているとスワップファイルが有るので、データベースの更新はできるが警告が出る

    Args:
        open_check が True なら未保存バッファが有れば、そちらに移動し無ければバッファを完全に閉じる
    Return:
        bool:
            True: success
            False: fail
    """
    if open_check:
        if opened_mail(False):
            print_warring('Can\'t remake database.\nBecase open the file.')
            return False
    # 未更新の閉じられたメール・ファイルのバッファを閉じる
    path = PATH + os.sep
    path_len = len(path)
    open_b = [i.buffer.number for i in vim.windows]  # 開いているバッファ・リスト
    for b in vim.buffers:
        n = b.number
        if b.options['modified'] is False \
                and n is not open_b \
                and os.path.expanduser(b.name)[:path_len] == path:
            vim.command('bwipeout ' + str(n))
    return shellcmd_popen(['notmuch', 'new'])


def opened_mail(draft):
    """ メールボックス内のファイルが開かれているか?

    Args:
        draft: フォルダもチェック対象にするか?
    Return:
        bool:
            True: if unsave, open buffer
            False: if all  saved, delete form buffer list
    """
    for info in vim_getbufinfo():
        filename = info['name'].decode()
        if draft:
            if get_mailbox_type() == 'Maildir':
                draft_dir = PATH + os.sep + '.draft'
            else:
                draft_dir = PATH + os.sep + 'draft'
            if filename.startswith(draft_dir + os.sep):
                continue
        if filename.startswith(PATH):
            if info['changed'] == 1:
                win_id = info['windows']
                if win_id:
                    win_id = win_id[0]
                    vim_win_gotoid(win_id)
                elif info['hidden']:
                    vim.command(vim.vars['notmuch_open_way']['edit'].decode() + ' ' + filename)
                return True
            vim.command('bwipeout ' + str(info['bufnr']))
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


def set_global_var():  # MailData で使用する設定依存の値をグローバル変数として保存
    # +{T-WIN} の colorcolumn 設定をする
    def get_display_format():
        global DISPLAY_FORMAT, DISPLAY_FORMAT2
        """ set display format and order in thread list."""
        def get_display_item():
            item = []
            for i in vim.vars['notmuch_display_item']:
                i = i.decode().lower()
                if i not in ['subject', 'from', 'date']:
                    print_warring('Error: setting g:notmuch_display_item.\nset default.')
                    return ['subject', 'from', 'date']
                item.append(i)
            if len(set(item)) != 3:
                print_warring('Error: setting g:notmuch_display_item.\nset default.')
                return ['subject', 'from', 'date']
            return item

        DISPLAY_FORMAT = '{0}'
        DISPLAY_FORMAT2 = ''
        for item in get_display_item():
            if item == 'subject':
                DISPLAY_FORMAT += '\t{1}'
                DISPLAY_FORMAT2 += '\t{0}'
            elif item == 'from':
                DISPLAY_FORMAT += '\t{2}'
                DISPLAY_FORMAT2 += '\t{1}'
            elif item == 'date':
                DISPLAY_FORMAT += '\t{3}'
                DISPLAY_FORMAT2 += '\t{2}'

    def set_subject_length(from_length, date_format):
        """ calculate Subject width in thread list."""
        def border_width():  # │ の幅を得る
            if vim.vars.get('notmuch_visible_line', 0) != 3:
                return 1
            for i in vim.Function('getcellwidths')():
                if i[0] >= 0x2502 and i[1] <= 0x2502:
                    return i[2]
            if vim.options['ambiwidth'] == b'double':
                return 2
            return 1

        def get_width():
            b = s_buf_num('thread', '')
            for t in vim.tabpages:
                for w in t.windows:
                    if w.buffer.number == b:
                        return w.width - 1
            return vim.options['column'] - 1

        if 'notmuch_subject_length' in vim.vars:
            return vim.vars['notmuch_subject_length'], from_length
        subject_length = 80 - from_length - 16 - 4
        width = get_width()
        time_length = len(datetime.datetime(2022, 10, 26, 23, 10, 10, 555555).strftime(date_format))
        # date_format によっては日付時刻が最も長くなりそうな 2022/10/26 23:10:10.555555 September, Wednesday
        width -= time_length + 6 + 3 * border_width() + 2
        # 最後の数字は、絵文字で表示するタグ、区切りのタブ*3, sing+ウィンドウ境界
        if subject_length < from_length * 2:
            subject_length = int(width * 2 / 3)
            from_length = width - subject_length
        else:
            subject_length = width - from_length
        visible_line = vim.vars.get('notmuch_visible_line', b'')
        if visible_line == 1 or visible_line == 2:
            colorcolumn = '7'
            n_colorcolumn = 7
            for i in vim.vars['notmuch_display_item'][0:2]:
                if i == b'subject':
                    n_colorcolumn += subject_length + 1
                elif i == b'from':
                    n_colorcolumn += from_length + 1
                elif i == b'date':
                    n_colorcolumn += time_length + 1
                colorcolumn += ',' + str(n_colorcolumn)
            vim.current.window.options['colorcolumn'] = colorcolumn
            if visible_line == 2:  # ColorColumn の色を Normal の反転色にする
                # Python では文字列の入れ替えができないので、Vim script関数を使う
                vim.Function('notmuch_py#ChangeColorColumn')()
        return subject_length, from_length

    global SENT_TAG, SUBJECT_LENGTH, FROM_LENGTH, DATE_FORMAT
    if 'notmuch_sent_tag' in vim.vars:  # 送信済みを表すタグ
        SENT_TAG = vim.vars['notmuch_sent_tag'].decode()
    else:
        SENT_TAG = 'sent'
    if 'notmuch_date_format' in vim.vars:  # スレッドに表示する Date の書式
        DATE_FORMAT = vim.vars['notmuch_date_format'].decode()
    else:
        DATE_FORMAT = '%Y-%m-%d %H:%M'
    if 'notmuch_from_length' in vim.vars:  # スレッドに表示する From の長さ
        FROM_LENGTH = vim.vars['notmuch_from_length']
    else:
        FROM_LENGTH = 21
    # スレッドに表示する Subject の長さ
    SUBJECT_LENGTH, FROM_LENGTH = set_subject_length(FROM_LENGTH, DATE_FORMAT)
    get_display_format()


def make_thread_core(search_term):
    laststatus = vim.options['laststatus']
    vim.options['laststatus'] = 2
    if 'statusline' in vim.current.window.options:
        statusline = vim.current.window.options['statusline']
    else:
        statusline = vim.options('statusline')
    progress = [  # 進行状況をステータスバーに表示するために必要となる情報
        0,  # 処理済み個数
        DBASE.count_messages(search_term),  # 全体個数
        '%#MatchParen#Searching ' + search_term + '...{0:>3}%%'
            + (vim_winwidth(0) - len('Searching ' + search_term + '...') - 4) * ' '  # 行末に追加する空白も含めた表示書式
            + '%<',
        vim_winwidth(0)  # ウィンドウ幅
    ]
    vim.current.window.options['statusline'] = 'Searching ' + search_term + '... 0%%'
    threads = DBASE.threads(search_term)
    reprint_folder()  # 新規メールなどでメール数が変化していることが有るので、フォルダ・リストはいつも作り直す
    set_global_var()
    # シングル・スレッド版
    ls = []
    for i in threads:
        ls.extend(make_single_thread(i, search_term, progress))
    # マルチプロセス版 Mailbox で Subject 全体を取得にしたら落ちる
    # threads = [i.threadid for i in threads]  # 本当は thread 構造体のままマルチプロセスで渡したいが、それでは次のように落ちる
    # # ValueError: ctypes objects containing pointers cannot be pickled
    # with ProcessPoolExecutor() as executor:
    #     f = [executor.submit(make_single_thread, i, search_term) for i in threads]
    #     for r in f:
    #         ls += r.result()
    sort_method = vim.vars.get('notmuch_sort', b'last').decode().split()
    if not check_sort_method(sort_method):
        sort_method = ['last']
    thread_change_sort_core(search_term, ls, sort_method)
    vim.options['laststatus'] = laststatus
    vim.current.window.options['statusline'] = statusline
    return True


# def make_single_thread(thread_id, search_term):  # マルチ・スレッド版
#     def make_reply_ls(ls, message, depth):  # スレッド・ツリーの深さ情報取得
#         ls.append((message.messageid, message, depth))
#         for msg in message.replies():
#             make_reply_ls(ls, msg, depth + 1)
#
#     thread = next(DBASE.threads('(' + search_term + ') and thread:' + thread_id))
#     # thread_id で検索しているので元々該当するのは一つ
#     try:  # スレッドの深さを調べる為のリスト作成開始 (search_term に合致しないメッセージも含まれる)
#         msgs = thread.toplevel()
#     except notmuch2.NullPointerError:
#         print_err('Error: get top-level message')
#     replies = []
#     for msg in msgs:
#         make_reply_ls(replies, msg, 0)
#     order = 0
#     ls = []
#     # search_term にヒットするメールに絞り込み
#     for reply in replies:
#         if DBASE.count_messages('(' + search_term + ') and id:"' + reply[0] + '"'):
#             depth = reply[2]
#             if depth > order:
#                 depth = order
#             ls.append(MailData(reply[1], thread, order, depth))
#             order = order + 1
#     return ls
def make_single_thread(thread, search_term, progress):
    def make_reply_ls(ls, message, depth):  # スレッド・ツリーの深さ情報取得
        ls.append((message, message, depth))
        for msg in message.replies():
            make_reply_ls(ls, msg, depth + 1)

    try:  # スレッドの深さを調べる為のリスト作成開始 (search_term に合致しないメッセージも含まれる)
        msgs = thread.toplevel()
    except notmuch2.NullPointerError:
        print_err('Error: get top-level message')
    replies = []
    for msg in msgs:
        make_reply_ls(replies, msg, 0)
    order = 0
    ls = []
    # search_term にヒットするメールに絞り込み
    for reply in replies:
        if reply[0].matched:
            depth = reply[2]
            if depth > order:
                depth = order
            ls.append(MailData(reply[1], thread, order, depth))
            order = order + 1
            progress[0] += 1
            p = progress[0] * 100 / progress[1]
            bar = progress[2].format(int(p))
            sep = int(progress[3] * p / 100) + 13
            if bar[sep:sep + 2] == '%%':
                sep += 1
            vim.current.window.options['statusline'] = bar[:sep] + '%*' + bar[sep + 1:]
            vim.command('redrawstatus')
    return ls


def set_subcmd_start():
    """ start して初めて許可するコマンドの追加 """
    cmd = vim.vars['notmuch_command']
    if 'open' not in cmd:  # start はいきなり呼び出し可能なので、open で判定
        cmd.update({
            'attach-delete': ['DeleteAttachment', 0x06],
            'attach-save': ['SaveAttachment', 0x06],
            'close': ['Close', 0x04],
            'close-tab': ['CloseTab', 0x04],
            'mail-attach-forward': ['ForwardMailAttach', 0x04],
            'mail-delete': ['DeleteMail', 0x06],
            'mail-edit': ['OpenOriginal', 0x06],
            'mail-export': ['ExportMail', 0x06],
            'mail-forward': ['ForwardMail', 0x04],
            'mail-import': ['ImportMail', 0x05],
            'mail-info': ['ViewMailInfo', 0x0c],
            'mail-move': ['MoveMail', 0x07],
            'mail-new': ['NewMail', 0x05],
            'mail-reply': ['ReplyMail', 0x04],
            'mail-reindex': ['ReindexMail', 0x06],
            'mail-resent-forward': ['ForwardMailResent', 0x04],
            'mail-save': ['SaveMail', 0x05],
            'mail-send': ['SendVim', 0x0c],
            'mark': ['MarkInThread', 0x04],
            'mark-command': ['CommandMarked', 0x05],
            'open': ['OpenSomething', 0x04],
            'view-previous': ['PreviousPage', 0x04],
            'view-unread-page': ['NextUnreadPage', 0x04],
            'view-unread-mail': ['NextUnread', 0x04],
            'view-previous-unread': ['PreviousUnread', 0x04],
            'reload': ['Reload', 0x04],
            'run': ['RunShellProgram', 0x07],
            'search': ['NotmuchSearch', 0x05],
            'search-thread': ['NotmuchThread', 0x04],
            'search-address': ['NotmuchAddress', 0x04],
            'search-duplication': ['NotmuchDuplication', 0x04],
            'search-refine': ['NotmuchRefine', 0x05],
            'search-up-refine': ['NotmuchUpRefine', 0x04],
            'search-down-refine': ['NotmuchDownRefine', 0x04],
            'tag-add': ['AddTags', 0x1f],
            'tag-delete': ['DeleteTags', 0x1f],
            'tag-toggle': ['ToggleTags', 0x1f],
            'tag-set': ['SetTags', 0x1f],
            'thread-connect': ['ConnectThread', 0x06],
            'thread-cut': ['CutThread', 0x06],
            'thread-next': ['NextThread', 0x04],
            'thread-toggle': ['ToggleThread', 0x04],
            'thread-sort': ['ThreadChangeSort', 0x05],
            'set-fcc': ['SetFcc', 0x09],
            'set-attach': ['SetAttach', 0x09],
            'set-encrypt': ['SetEncrypt', 0x09],
        })


def set_subcmd_newmail():
    """ mail-new して初めて許可するコマンドの追加 """
    cmd = vim.vars['notmuch_command']
    if 'mail-send' not in cmd:  # mail-new はいきなり呼び出し可能なので、mail-send で判定
        cmd.update({
            'start': ['StartNotmuch', 0x0c],
            'mail-send': ['SendVim', 0x0c],
            'mail-info': ['ViewMailInfo', 0x0c],
            'tag-add': ['AddTags', 0x1f],
            'tag-delete': ['DeleteTags', 0x1f],
            'tag-toggle': ['ToggleTags', 0x1f],
            'tag-set': ['SetTags', 0x1f],
            'set-fcc': ['SetFcc', 0x09],
            'set-attach': ['SetAttach', 0x09],
            'set-encrypt': ['SetEncrypt', 0x09],
        })


def set_folder_format():
    def set_open_way(len):
        v_o = vim.options
        max_len = v_o['columns'] - len
        lines = v_o['lines']
        showtabline = v_o['showtabline']
        laststatus = v_o['laststatus'] if 1 else 0
        height = (lines - (showtabline == 2) - laststatus) * 3 / 4  # スレッドは1/4
        # ただし最低5件は表示する
        tab_status = 7 + (showtabline != 0) + laststatus
        if lines - height < tab_status:
            height = lines - tab_status
        height = int(height)
        if 'notmuch_open_way' not in vim.vars:
            vim.vars['notmuch_open_way'] = {}
        open_way = vim.vars['notmuch_open_way']
        # 設定が有れば new, vnew, tabedit, tabnew, enew 限定
        for k, v in open_way.items():
            if k == b'open':
                continue
            v = v.decode()
            if re.match(r'(((rightbelow|belowright|topleft|botright)\s+)?\d*(new|vnew)|tabedit|tabnew|enew)',
                        v) is None:
                del open_way[k]  # 条件に一致しない設定削除
                print_warring("For g:notmuch_open_way[" + k.decode()
                              + "], if the setting is 'tabedit/enew', "
                              + "no other words/spaces can\'t be included.")
        if 'folders' not in open_way:
            open_way['folders'] = 'tabedit'
        if 'thread' not in open_way:
            open_way['thread'] = 'rightbelow ' + str(max_len) + 'vnew'
        if 'show' not in open_way:
            open_way['show'] = 'belowright ' + str(height) + 'new'
        if 'edit' not in open_way:
            open_way['edit'] = 'tabedit'
        if 'draft' not in open_way:
            open_way['draft'] = 'tabedit'
        if 'search' not in open_way:
            open_way['search'] = 'tabedit'
        if 'view' not in open_way:
            open_way['view'] = 'belowright ' + str(height) + 'new'

    max_len = 0
    for s in vim.vars['notmuch_folders']:
        s_len = len(s[0].decode())
        if s_len > max_len:
            max_len = s_len
    if 'notmuch_folder_format' not in vim.vars:
        try:
            db = notmuch2.Database()
        except NameError:
            db.close()
            raise notmuchVimError('Do\'not open notmuch Database: \'' + PATH + '\'.')
        vim.vars['notmuch_folder_format'] = '{0:<' + str(max_len) + '} ' + \
            '{1:>' + str(len(str(db.count_messages('tag:unread'))) + 1) + '}/' + \
            '{2:>' + str(len(str(int(db.count_messages('path:**') * 1.2)))) + '}│' + \
            '{3:>' + str(len(str(db.count_messages('tag:flagged'))) + 1) + '} ' + \
            '[{4}]'
        # ↑上から順に、未読/全/重要メールの数の桁数計算、末尾付近の * 1.2 や + 1 は増加したときのために余裕を見ておく為
        db.close()
    set_open_way(vim_strdisplaywidth(vim.vars['notmuch_folder_format'].decode().format('', 0, 0, 0, '')) - 1)


def format_folder(folder, search_term):
    global DBASE
    try:  # search_term チェック
        all_mail = DBASE.count_messages(search_term)  # メール総数
    except notmuch2.XapianError:
        print_error('notmuch2.XapianError: Check search term: ' + search_term)
        vim.command('message')  # 起動時のエラーなので、再度表示させる
        return '\'search term\' (' + search_term + ') error'
    return vim.vars['notmuch_folder_format'].decode().format(
        folder,                                                         # 擬似的なフォルダー・ツリー
        DBASE.count_messages('(' + search_term + ') and tag:unread'),   # 未読メール数
        all_mail,
        DBASE.count_messages('(' + search_term + ') and tag:flagged'),  # 重要メール数
        search_term                                                     # 検索方法
    )


def print_folder():
    global DBASE
    """ vim から呼び出された時にフォルダ・リストを書き出し """
    try:
        DBASE = notmuch2.Database()
    except NameError:
        return
    b = vim.buffers[s_buf_num('folders', '')]
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
    # StartNotmuch() が呼ぼれずに mail-new がされていると buf_num が未定義なので直ちに処理を返す
    if not ('folders' in s_buf_num_dic()):
        return
    b = vim.buffers[s_buf_num('folders', '')]
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
    global DBASE
    notmuch_new(False)
    DBASE = notmuch2.Database()
    reprint_folder()
    DBASE.close()


def set_folder_b_vars(v):
    global DBASE
    """ フォルダ・リストのバッファ変数セット """
    v['all_mail'] = DBASE.count_messages('')
    v['unread_mail'] = DBASE.count_messages('tag:unread')
    v['flag_mail'] = DBASE.count_messages('tag:flagged')


def rm_file(dirname):
    """ ファイルやディレクトリをワイルドカードで展開して削除 """
    rm_file_core(dirname + '*' + os.sep + '*' + os.sep + '.*')
    rm_file_core(dirname + '*' + os.sep + '*' + os.sep + '*')
    rm_file_core(dirname + '*' + os.sep + '.*')
    rm_file_core(dirname + '*' + os.sep + '*')
    rm_file_core(dirname + '.*')
    rm_file_core(dirname + '*')


def rm_file_core(files):
    for name in glob.glob(files):
        if os.path.isfile(name):
            os.remove(name)
        else:
            os.rmdir(name)


def reload():
    type = buf_kind()
    v = vim.current
    line = v.window.cursor[0] - 1
    v = v.buffer.vars['notmuch']
    if type == 'show' or type == 'view':
        if ('search_term' in v) and ('msg_id' in v):
            reload_show()
        return
    if type == 'folders':
        if is_same_tabpage('thread', ''):
            thread = s_buf_num('thread', '')
            if [x for x in vim.buffers if x.number == thread][0].vars['notmuch']['search_term'].decode() == \
                    vim.vars['notmuch_folders'][line][1]:  # search_term が folder, thread で同じならリロード
                reload_thread()
            else:  # search_term が folder, thread で異なるなら開く (同じ場合はできるだけ開いているメールを変えない)
                open_thread_from_vim(False, True)
    elif type == 'thread' or type == 'search':
        reload_thread()


def open_something(args):
    type = buf_kind()
    if type == 'folders':
        open_thread_from_vim(True, False)
    elif type == 'thread' or type == 'search':
        open_mail()
    elif type == 'show' or type == 'view':
        open_attachment(args)


def print_thread_view(search_term):
    """ vim 外からの呼び出し時のスレッド・リスト書き出し """
    global DBASE
    if not (search_term in THREAD_LISTS.keys()):
        DBASE = notmuch2.Database()
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


def get_unread_in_THREAD_LISTS(search_term):
    global DBASE
    """ THREAD_LISTS から未読を探す """
    return [i for i, x in enumerate(THREAD_LISTS[search_term]['list'])
            if get_message('id:' + x._msg_id) is not None  # 削除済みメール・ファイルがデータベースに残っていると起きる
            and ('unread' in DBASE.find(x._msg_id).tags)]


def open_thread_from_vim(select_unread, remake):  # 実際にスレッドを印字←フォルダ・リストがアクティブ前提
    line = vim.current.window.cursor[0]
    vim.command('MakeThreadList()')
    open_thread(line, select_unread, remake)
    if is_same_tabpage('show', ''):
        open_mail()


def open_thread(line, select_unread, remake):
    """ フォルダ・リストからスレッドリストを開く """
    folder, search_term = vim.vars['notmuch_folders'][line - 1]
    folder = folder.decode()
    search_term = search_term.decode()
    if not check_search_term(search_term):
        return
    b_num = s_buf_num('thread', '')
    if folder == '':
        vim_sign_unplace(b_num)
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
        vim_goto_bufwinid(s_buf_num("folders", ''))
        notmuch_search([])
    b_v = vim.current.buffer.vars['notmuch']
    if vim_goto_bufwinid(b_num) \
            and not remake \
            and ('search' in b_v) \
            and b_v['search_term'].decode() == search_term:
        return
    print_thread(b_num, search_term, select_unread, remake)


def print_thread(b_num, search_term, select_unread, remake):
    """ スレッド・リスト書き出し """
    global DBASE
    DBASE = notmuch2.Database()
    print_thread_core(b_num, search_term, select_unread, remake)
    change_buffer_vars_core()
    DBASE.close()
    # vim.command('redraw!')


def fold_open_core():
    if vim_foldlevel(vim.current.window.cursor[0]):
        vim.command('normal! zO')


def fold_open():
    c = vim.current
    fold_open_core()
    reset_cursor_position(c.buffer, c.window.cursor[0])


def print_thread_core(b_num, search_term, select_unread, remake):
    def set_vartabstop(b):
        if vim.vars.get('notmuch_visible_line', 0) != 3:
            return
        border_w = 1
        if vim.options['ambiwidth'] == b'double':
            border_w = 2
        for i in vim.Function('getcellwidths')():
            if i[0] >= 0x2502 and i[1] <= 0x2502:
                border_w = i[2]
                break
        if border_w != 2:
            return
        ts = '8,'
        for i in vim.vars.get('notmuch_display_item', ['subject', 'from', 'date']):
            if i == b'subject':
                ts = ts + str(SUBJECT_LENGTH + 2) + ','
            elif i == b'date':
                ts = ts + str(len(
                    datetime.datetime(2022, 10, 26, 23, 10, 10, 555555).strftime(DATE_FORMAT)) + 2) \
                    + ','
            elif i == b'from':
                ts = ts + str(FROM_LENGTH + 2) + ','
        b.options['vartabstop'] = ts + '1'

    global DBASE
    if search_term == '':
        return
    try:  # search_term チェック
        unread = DBASE.count_messages(search_term)
    except notmuch2.XapianError:
        print_error('notmuch2.XapianError: Check search term: ' + search_term + '.')
        return
    b = vim.buffers[b_num]
    vim_sign_unplace(b_num)
    if remake or not (search_term in THREAD_LISTS):
        if not make_thread_core(search_term):
            return
        threadlist = THREAD_LISTS[search_term]['list']
    else:
        threadlist = THREAD_LISTS[search_term]['list']
    b.options['modifiable'] = 1
    flag = not ('list' in THREAD_LISTS[search_term]['sort'])
    # マルチプロセスだと、vim.buffers[num] や vim.current.buffer.number だとプロセスが違うので、異なる数値になり上手くいかない
    # マルチスレッドは速くならない
    # 出力部分の作成だけマルチプロセス化するバージョン←やはり速くならない
    # マルチスレッドも速くならない
    b.vars['notmuch']['search_term'] = search_term
    b[:] = None
    vim.command('redraw')  # 直前より行数の少ないスレッドを開いた時、後に選択する行がウィンドウ先頭に表示されるのを防ぐ
    ls = [msg.get_list(flag) for msg in threadlist]
    # 下の様はマルチプロセス化を試みたが反って遅くなる
    # with ProcessPoolExecutor() as executor:  # ProcessPoolExecutor
    #     f = [executor.submit(i.get_list, flag) for i in threadlist]
    #     for r in f:
    #         ls.append(r.result())
    vim_win_gotoid(vim_bufwinid(b.number))  # これがないと直前より行数の多いスレッドを開くと固まる場合が有る (すぐ下のスレッドも条件?)
    b.append(ls)
    b[0] = None
    b.options['modifiable'] = 0
    print('Read data: [' + search_term + ']')
    if b_num == s_buf_num('thread', ''):
        kind = 'thread'
    else:
        kind = 'search'
    reopen(kind, search_term)
    set_vartabstop(b)
    if select_unread:
        index = get_unread_in_THREAD_LISTS(search_term)
        unread = DBASE.count_messages('(' + search_term + ') and tag:unread')
        if index:
            reset_cursor_position(b, index[0] + 1)
            fold_open()
        elif unread:  # フォルダリストに未読はないが新規メールを受信していた場合
            print_thread_core(b_num, search_term, True, True)
        else:
            vim.command('keepjump normal! Gzb')
            reset_cursor_position(b, vim.current.window.cursor[0])
            fold_open()
    b_name = b.name
    vim.command('silent file! notmuch://thread?' + search_term.replace('#', r'\#'))
    vim.command('filter(v:oldfiles, (_, v) => v !~ "^notmuch://")')
    Bwipeout(b_name)


def check_sort_method(sort):
    ret = True
    while True:
        ls = list(set(sort))
        for i in ls:
            if sort.count(i) > 1:
                for j in range(sort.count(i) - 1):
                    sort.remove(i)
            if i not in ['list', 'tree', 'Date', 'date',
                         'Last', 'last', 'From', 'from', 'Subject', 'subject']:
                sort.remove(i)
                print_warring('No sort method: ' + i)
                ret = False
        else:
            break
    if (len(sort) > 2
            or (not ('tree' in sort) and not ('list' in sort) and len(sort) > 1)
            or (('tree' in sort) and ('list' in sort))):
        print_warring('Too many arguments: ' + ' '.join(sort))
        return False
    elif sort == []:
        return False
    return ret


def thread_change_sort_core(search_term, ls, sort):
    if 'list' in sort:
        if 'Subject' in sort:
            ls.sort(key=attrgetter('_reformed_subject'), reverse=True)
        elif 'subject' in sort:
            ls.sort(key=attrgetter('_reformed_subject'))
        elif 'Date' in sort or 'Last' in sort:
            ls.sort(key=attrgetter('_date'), reverse=True)
        # elif 'date' in sort or 'last' in sort:
        #     ls.sort(key=attrgetter('_date'))
        elif 'From' in sort:
            ls.sort(key=attrgetter('_from'), reverse=True)
        elif 'from' in sort:
            ls.sort(key=attrgetter('_from'))
        else:
            ls.sort(key=attrgetter('_date'))
    else:
        if 'Subject' in sort:
            ls.sort(key=attrgetter('_thread_subject', '_thread_id', '_thread_order'), reverse=True)
        elif 'subject' in sort:
            ls.sort(key=attrgetter('_thread_subject', '_thread_id', '_thread_order'))
        elif 'Date' in sort:
            ls.sort(key=attrgetter('_oldest', '_thread_id', '_thread_order'), reverse=True)
        elif 'date' in sort:
            ls.sort(key=attrgetter('_oldest', '_thread_id', '_thread_order'))
        # elif 'last' in sort:
        #     ls.sort(key=attrgetter('_latest', '_thread_id', '_thread_order'))
        elif 'Last' in sort:
            ls.sort(key=attrgetter('_latest', '_thread_id', '_thread_order'), reverse=True)
        elif 'From' in sort:
            ls.sort(key=attrgetter('_authors', '_thread_id', '_thread_order'), reverse=True)
        elif 'from' in sort:
            ls.sort(key=attrgetter('_authors', '_thread_id', '_thread_order'))
        else:
            ls.sort(key=attrgetter('_latest', '_thread_id', '_thread_order'))
    THREAD_LISTS[search_term] = {'list': ls, 'sort': sort}


def thread_change_sort(sort_method):
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
    if bufnr != s_buf_num('thread', '') \
            and not (search_term in s_buf_num('search', '')
                     and bufnr == s_buf_num('search', search_term)):
        return
    sort_method = sort_method[2:]
    if not check_sort_method(sort_method):
        sort_method = vim_input_ls('sort method: ', ' '.join(sort_method), 'customlist,notmuch_py#CompSort')
        if sort_method == []:
            return
    if sort_method == ['list']:
        if 'list' in THREAD_LISTS[search_term]['sort']:
            return  # 結局同じ表示方法
        else:
            sort_method.extend(THREAD_LISTS[search_term]['sort'])
    elif sort_method == ['tree']:
        sort_method = copy.deepcopy(THREAD_LISTS[search_term]['sort'])
        if 'list' in sort_method:
            sort_method.remove('list')
        else:
            return  # 結局同じ表示方法
    elif 'tree' in sort_method:
        sort_method.remove('tree')
    if sort_method == THREAD_LISTS[search_term]['sort']:
        return
    vim_sign_unplace(bufnr)
    thread_change_sort_core(search_term, THREAD_LISTS[search_term]['list'], sort_method)
    b.options['modifiable'] = 1
    flag = not ('list' in sort_method)
    # マルチスレッド 速くならない
    # with ThreadPoolExecutor() as executor:
    #     for i, msg in enumerate(threadlist):
    #         executor.submit(print_thread_line, b, i, msg, flag)
    # マルチスレッドしていないバージョン
    b[:] = None
    ls = []
    for msg in THREAD_LISTS[search_term]['list']:
        ls.append(msg.get_list(flag))
    b.append(ls)
    b[0] = None
    b.options['modifiable'] = 0
    index = [i for i, msg in enumerate(THREAD_LISTS[search_term]['list']) if msg._msg_id == msg_id]
    vim.command('keepjump normal! Gzb')
    if index:  # 実行前のメールがリストに有れば選び直し
        reset_cursor_position(b, index[0] + 1)
    else:
        print('Don\'t select same mail.\nBecase already Delete/Move/Change folder/tag.')
        vim.command('keepjump normal! G')
    fold_open()


def change_buffer_vars():
    """ スレッド・リストのバッファ変数更新 """
    change_buffer_vars_core()
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
        msg = THREAD_LISTS[b_v['search_term'].decode()]['list'][vim.current.window.cursor[0] - 1]
        msg_id = msg._msg_id
        b_v['msg_id'] = msg_id
        b_v['subject'] = msg.get_subject()
        b_v['date'] = msg.get_date()
        emoji_tags = ''
        tags = copy.copy(msg._tags)
        for t, emoji in {'unread': '📩', 'draft': '📝', 'flagged': '⭐',
                         'Trash': '🗑', 'attachment': '📎',
                         'encrypted': '🔑', 'signed': '🖋️'}.items():
            if t in tags:
                emoji_tags += emoji
                tags.remove(t)
        b_v['tags'] = emoji_tags + ' '.join(tags)


def vim_escape(s):
    """ Vim と文字列をやり取りする時に、' をエスケープする """
    # return s.replace('\\', '\\\\').replace("'", "''")
    return s.replace("'", "''")


def replace_charset(s):  # 日本/中国語で上位互換の文字コードに置き換える
    if s == 'iso-2022-jp':
        return 'iso-2022-jp-3'
    elif s == 'gb2312' or s == 'gbk':  # Outlook からのメールで実際には拡張された GBK や GB 1830 を使っているのに
        # Content-Type: text/plain; charset='gb2312'
        # で送られることに対する対策
        # https://ifritjp.github.io/blog/site/2019/02/07/outlook.html
        # http://sylpheed-support.good-day.net/bbs_article.php?pthread_id=744
        # 何故か日本語メールもこの gb2312 として送られてくるケースも多い
        return 'gb18030'  # 一律最上位互換の文字コード GB 1830 扱いにする
    else:
        return s


def is_same_tabpage(kind, search_term):
    # おそらく vim.current.tabpage.number と比較する必要はないけど win_id2tabwin() の仕様変更などが起きた時用に念の為
    if not (kind in s_buf_num_dic()):
        return False
    if kind == 'folders' or kind == 'thread' or kind == 'show':
        return vim_win_id2tabwin(kind, '') == vim.current.tabpage.number
    # kind == search or view
    elif search_term == '':
        return False
    else:
        if not (search_term in s_buf_num(kind, '')):
            return False
        return vim_win_id2tabwin(kind, search_term) == vim.current.tabpage.number


def reload_show():
    global DBASE
    b = vim.current.buffer
    print('reload', b.options['filetype'].decode()[8:])
    DBASE = notmuch2.Database(mode=notmuch2.Database.MODE.READ_WRITE)
    b_v = b.vars['notmuch']
    open_mail_by_msgid(b_v['search_term'].decode(),
                       b_v['msg_id'].decode(), b.number, True)
    DBASE.close()


def reload_thread():
    global DBASE
    # if opened_mail(False):
    #     print_warring('Please save and close mail.')
    #     return
    b = vim.current.buffer
    search_term = b.vars['notmuch']['search_term'].decode()
    if search_term == '*':
        notmuch_duplication(True)
        return
    notmuch_new(False)
    w = vim.current.window
    # 再作成後に同じメールを開くため Message-ID を取得しておく
    msg_id = get_msg_id()
    DBASE = notmuch2.Database()  # ここで書き込み権限 ON+関数内で OPEN のままにしたいが、そうすると空のスレッドで上の
    # search_term = b.vars['notmuch']['search_term'].decode()
    # で固まる
    print_thread_core(b.number, search_term, False, True)
    if msg_id != '':
        index = [i for i, msg in enumerate(
            THREAD_LISTS[search_term]['list']) if msg._msg_id == msg_id]
    # else:  # 開いていれば notmuch-show を一旦空に←同一タブページの時は vim script 側メールを開くので不要
    # ただし、この関数内でその処理をすると既読にしてしまいかねないので、ここや print_thread() ではやらない
    if b[0] == '':  # リロードの結果からのスレッド空←スレッドなので最初の行が空か見れば十分
        change_buffer_vars_core()
        if 'show' in s_buf_num_dic():
            empty_show()
        return
    # ウィンドウ下部にできるだけ空間表示がない様にする為一度最後のメールに移動後にウィンドウ最下部にして表示
    vim.command('keepjump normal! Gzb')
    if msg_id != '' and len(index):  # 実行前のメールがリストに有れば選び直し
        reset_cursor_position(b, index[0] + 1)
    else:
        print('Don\'t select same mail.\nBecase already Delete/Move/Change folder/tag.')
    change_buffer_vars_core()
    DBASE.close()
    if b[0] != '':
        fold_open()
        if is_same_tabpage('show', ''):
            # タグを変更することが有るので書き込み権限も
            DBASE = notmuch2.Database(mode=notmuch2.Database.MODE.READ_WRITE)
            open_mail_by_msgid(
                search_term,
                THREAD_LISTS[search_term]['list'][w.cursor[0] - 1]._msg_id,
                b.number, False)
            DBASE.close()


def cursor_move_thread(search_term):
    type = buf_kind()
    if type == 'thread':
        buf_num = s_buf_num('thread', '')
    elif type == 'search':
        buf_num = s_buf_num('search', search_term)
    else:
        return
    b = vim.current.buffer
    if b.number != buf_num or get_msg_id() == '' or b.vars['notmuch']['msg_id'].decode() == get_msg_id():
        return
    change_buffer_vars()
    if is_same_tabpage('show', '') or is_same_tabpage('view', search_term):
        open_mail()


def reopen(kind, search_term):
    """ スレッド・リスト、メール・ヴューを開き直す """
    if type(search_term) is bytes:
        search_term = search_term.decode()
    # まずタブの移動
    vim.command('ChangeExistTabpage("' + kind + '", \'' + vim_escape(search_term) + '\')')
    if kind == 'search' or kind == 'view':
        buf_num = s_buf_num(kind, search_term)
    else:
        buf_num = s_buf_num(kind, '')
    if not vim_goto_bufwinid(buf_num):  # 他のタプページにもなかった
        # if kind == 'thread':
        #     vim_goto_bufwinid(s_buf_num("folders", '')) | silent only')
        open_way = vim.vars['notmuch_open_way'][kind].decode()
        if open_way == 'enew':
            vim.command('silent buffer ' + str(buf_num))
        elif open_way == 'tabedit' or open_way == 'tabnew':
            vim.command('silent tab sbuffer ' + str(buf_num))
        else:
            open_way = re.sub(r'\bnew\b', 'split', open_way)
            open_way = re.sub(r'([0-9]+)new\b', ':\\1split', open_way)
            open_way = re.sub(r'\bvnew\b', 'vsplit', open_way)
            open_way = re.sub(r'([0-9]+)vnew\b', ':\\1vsplit', open_way)
            vim.command(open_way)
            vim.command('silent buffer ' + str(buf_num))
        if kind == 'thread':
            open_way = vim.vars['notmuch_open_way']['show'].decode()
            if open_way != 'enew' and open_way != 'tabedit' and open_way != 'tabnew':
                vim.command('MakeShow()')
        elif kind == 'search':
            open_way = vim.vars['notmuch_open_way']['view'].decode()
            if open_way != 'enew' and open_way != 'tabedit' and open_way != 'tabnew':
                vim.command('call s:MakeView(\'' + vim_escape(search_term) + '\')')
        vim_goto_bufwinid(buf_num)


def open_mail():
    # h = list(vim.vars['notmuch_show_headers']) + \
    #     [b'Attach', b'Decrypted', b'Encrypt', b'Fcc', b'HTML', b'Signature']
    # print(h)
    # for i in vim.vars['notmuch_show_hide_headers']:
    #     if i in~ h:
    #         print(type(i), i)
    b = vim.current
    w = b.window
    b = b.buffer
    search_term = b.vars['notmuch']['search_term'].decode()
    index = w.cursor[0] - 1
    if search_term == '' or w.buffer[index] == '':
        if is_same_tabpage('show', ''):
            empty_show()
        return
    open_mail_by_index(search_term, index, b.number)


def open_mail_by_index(search_term, index, active_win):
    """ 実際にメールを表示 """
    global DBASE
    # タグを変更することが有るので書き込み権限も
    DBASE = notmuch2.Database(mode=notmuch2.Database.MODE.READ_WRITE)
    threadlist = THREAD_LISTS[search_term]['list']
    msg_id = threadlist[index]._msg_id
    open_mail_by_msgid(search_term, msg_id, active_win, False)
    DBASE.close()


def decode_string(s, charset, error):
    ''' 呼び出し元で Python でデコード失敗した時に、nkf や iconv でデコード '''
    if charset == 'iso-2022-jp-3' and shutil.which('nkf') is not None:
        ret = run(['nkf', '-w', '-J'], input=s, stdout=PIPE)
        return ret.stdout.decode()
    elif vim_has('iconv'):
        return vim.Function('iconv')(s, charset, 'utf-8').decode()
    elif shutil.which('iconv') is not None:
        ret = run(['iconv', '-f', charset, '-t', 'utf-8'], input=s, stdout=PIPE)
        if ret.returncode:
            return s.decode(charset, 'replace')
        return ret.stdout.decode()
    else:
        return s.decode(charset, 'replace')


def get_message(s):
    '''
    * search-term: s にヒットする notmuch2.Message を返す
    * 見つからないときは None
    * 見つかったときは最初の一つ
    '''
    if DBASE.count_messages(s) == 0:
        return None
    return next(DBASE.messages(s))


def open_mail_by_msgid(search_term, msg_id, active_win, mail_reload):
    """ open mail by Message-ID (not threader order)
    save caller buffer variable before open
    """
    class Output:
        def __init__(self):
            self.main = {  # 通常の本文
                'header': [],      # ヘッダー
                'attach': [],      # (Attach/Del-Attach ヘッダ, b.notmuch['attachments'] に使うデータ) とタプルのリスト
                # b.notmuch['attachments'] は [filename, [part_num], part_string]
                # [part_num]:  msg.walk() していく順序、もしくは
                #              * [-1] ローカルファイル
                #              * [1, 1] のように複数ある時は暗号化/ローカル内の添付ファイル
                # part_string: ローカルファイルならそのディレクトリ
                #              そうでなければ、msg.walk() した時のメッセージ・パート
                'content': []     # 本文
            }
            self.html = {  # HTML パート
                'content': [],  # 本文
                'part_num': 0   # HTML パートの数
            }
            self.changed_subject = False  # 暗号化されていた Subject 複合し書き換えをしたか?
            self.next = None  # 次の要素

    def check_end_view():  # メール終端まで表示しているか?
        if vim.bindeval('line("w$")') == len(vim.current.buffer):  # 末尾まで表示
            # ただしメールなので、行が長く折り返されて表示先頭行と最終行が同一の場合は考慮せず
            return True
        else:
            return False

    def get_msg():  # 条件を満たす Message とそのメール・ファイル名を取得
        global DBASE
        # ファイルが全て消されている場合は、None, None を返す
        b_v['search_term'] = search_term
        msg = get_message('(' + search_term + ') and id:"' + msg_id + '"')
        if msg is None:  # 同一条件+Message_ID で見つからなくなっているので Message_ID だけで検索
            print('Already Delete/Move/Change folder/tag')
            try:
                msg = DBASE.find(msg_id)
            except LookupError:
                return None, None
        for f in msg.filenames():
            if os.path.isfile(f):
                b_v['msg_id'] = msg_id
                b_v['subject'] = get_msg_header(open_email_file(f), 'Subject')
                b_v['date'] = RE_TAB2SPACE.sub(
                    ' ', datetime.datetime.fromtimestamp(msg.date).strftime(DATE_FORMAT))
                b_v['tags'] = get_msg_tags(msg)
                if active_win != b_w.number \
                        and (is_same_tabpage('thread', '') or is_same_tabpage('search', search_term)):
                    thread_b_v['msg_id'] = msg_id
                    thread_b_v['subject'] = b_v['subject']
                    thread_b_v['date'] = b_v['date']
                    thread_b_v['tags'] = b_v['tags']
                return msg, f
            else:  # メール・ファイルが存在しなかったので、再インデックスが必要
                # やらないとデータベース上に残る存在しないファイルからの情報取得でエラー発生
                DBASE.close()
                reindex_mail(msg_id, '', '')
                DBASE = notmuch2.Database(mode=notmuch2.Database.MODE.READ_WRITE)
                msg = DBASE.find(msg_id)
        return None, None

    def header(msg, output, notmuch_headers):  # vim からの呼び出し時に msg に有るヘッダ出力
        for header in notmuch_headers:
            if type(header) is bytes:
                header = header.decode()
            h_cont = msg.get_all(header)
            if h_cont is None:
                continue
            data = ''
            for d in h_cont:
                data += d
            data = decode_header(data, False, msg.get_content_charset())
            if data != '':
                data = data.replace('\t', ' ')
                data = header + ': ' + data
                output.main['header'].append(data)

    def get_virtual_header(msg_file, output, header):
        attachments = msg_file.get_all(header)
        if attachments is None:
            return
        for f in attachments:
            f = decode_header(f, True, msg_file.get_content_charset())
            if f == '':
                continue
            f = os.path.expandvars(os.path.expanduser(f))
            tmp_dir, name = os.path.split(f)
            if os.path.isfile(f):
                output.main['attach'].append(('Attach: ' + name, [name, [-1], tmp_dir + os.sep]))
            else:
                output.main['attach'].append(('Del-Attach: ' + name, None))

    def add_content(s_list, s):  # 文字列 s をリストに変換して s_list に追加
        if s == '':
            return
        s = re.sub('[\u200B-\u200D\uFEFF]', '', s)  # ゼロ幅文字の削除
        s_l = re.split('[\n\r\v\x0b\x1d\x1e\x85\u2028\u2029]',
                       s.replace('\r\n', '\n').replace('\x1c', '\f'))
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
        # b = vim.current.buffer
        while s_l[-1] == '':
            del s_l[-1]
        for i in s_l:
            s_list.append(re.sub(r'^\s+$', '', i))

    def vim_append_content(out):  # 複数行を vim のカレントバッファに書き込みとカーソル位置の指定
        # Attach, HTML ヘッダや本文開始位置を探す
        header_line = len(out.main['header']) + 1
        for s in out.main['attach'] + [('', '')]:
            if re.match(r'(Attach|HTML|Encrypt|PGP-Public-Key|(Good-|Bad-)?Signature):',
                        s[0]) is not None:
                break
            header_line += 1
        # 折り畳んで表示するヘッダの位置取得
        hide = '^('
        for h in vim.vars['notmuch_show_hide_headers']:
            hide += h.decode() + '|'
        hide = hide[:-1] + ')'
        fold_begin = [i for i, x in enumerate(out.main['header'])
                      if (re.match(hide, x) is not None)]
        if len(fold_begin) >= 2:  # 連続して 2 つ以上無いと折りたたみにならない
            fold_begin = [fold_begin[0] + 1]
        else:
            fold_begin = []
        # 必要に応じて thread_b のサブジェクト変更
        for s in out.main['header']:
            match = re.match(r'^Subject:\s*', s)
            if match is None:
                continue
            else:
                s = s[match.end():]
                thread_s = thread_b_v['subject'].decode()
                if s != thread_s:
                    b_v['subject'] = s
                    reset_subject(s)
                break
        # 出力データの生成
        ls = []
        while out is not None:
            ls += out.main['header']
            for t in out.main['attach']:
                if t[1] is not None:
                    b_v['attachments'][str(len(ls) + 1)] = t[1]
                ls.append(t[0])
            ls.append('')
            if not out.main['content']:
                ls[-1] = '\fHTML mail'
                ls += out.html['content']
            else:
                ls += out.main['content']
                if out.html['content']:
                    fold_begin.append(len(ls) + 2)  # text/plain がある時は折りたたむので開始行記録
                    ls.append('')
                    ls.append('\fHTML part')
                    ls += out.html['content']
            out = out.next
        # 折り畳みに関係する message/rfc822 などの開始位置の探索
        fold = [i for i, x in enumerate(ls) if (re.match(r'^\f', x) is not None)]
        if fold:
            b.vars['notmuch']['fold_line'] = fold[0] + 1
        else:
            b.vars['notmuch']['fold_line'] = 0
        # データ出力
        b.options['modifiable'] = 1
        b.append(ls, 0)
        b[len(ls):] = None
        b.options['modifiable'] = 0
        # 折り畳みとカーソル位置指定
        for i in fold_begin:
            b_w.cursor = (i, 0)
            vim.command('normal! zc')
        b_w.cursor = (1, 0)  # カーソル位置が画面内だと先頭が表示されないので、一度先頭に移動
        vim.command('redraw')
        if len(ls) < header_line:
            b_w.cursor = (1, 0)  # カーソルを先頭
        else:
            b_w.cursor = (header_line, 0)  # カーソルを添付ファイルや本文位置にセット

    def get_mail_context(part, charset, encoding):  # メールの本文をデコードして取り出す
        charset = replace_charset(charset)
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
                    content = '\n'.join(line[0:b_con]) \
                        + b64decode('\n'.join(line[b_con:b_sig])).decode(charset) \
                        + '\n'.join(line[b_sig:])
                    return content, undecode_payload
                elif encoding == 'quoted-printable':
                    content = '\n'.join(line[0:b_con]) \
                        + decodestring('\n'.join(line[b_con:b_sig])).decode(charset) \
                        + '\n'.join(line[b_sig:])
                    return content, undecode_payload
            if encoding == 'base64':
                decode_payload = payload.decode(charset, 'replace')
            else:
                decode_payload = undecode_payload
            try:
                return payload.decode(charset), decode_payload
            except UnicodeDecodeError:
                return decode_string(payload, charset, 'replace'), decode_payload
            except LookupError:
                print_warring('unknown encoding ' + charset + '.')
                payload = part.get_payload()
                return payload, decode_payload

    def get_attach(part, part_ls, out, header, name):
        if part.is_multipart():  # is_multipart() == True で呼び出されている (message/rfc822 の場合)
            if is_delete_rfc(part):
                out.main['attach'].append(('Del-' + header + name, None))
                return
        elif part.get_payload() == '':
            out.main['attach'].append(('Del-' + header + name, None))
            return
        if len(part_ls) >= 2:
            out.main['attach'].append((header + name, [name, vim.List(part_ls), part.as_string()]))
        else:
            out.main['attach'].append((header + name, [name, vim.List(part_ls), '']))

    def select_header(part, part_ls, pgp, out):
        attachment = decode_header(part.get_filename(), True, part.get_content_charset())
        # ↑filename が filename*より先に有ると RFC2231 に準拠せず、filename が使われる
        if attachment != '':  # → 空文字でなければ、filename* の検索を試みる
            match = re.search(r"filename\*=(?P<charset>[^']*)'(?P<lang>[^']*)'(?P<encoded_text>[^;]*)",
                              part.get("Content-Disposition"))
            if match:
                try:
                    attachment = unquote(match.group('encoded_text'), encoding=match.group('charset'))
                except Exception:  # フォールバック
                    pass
            #         attachment = decode_header(part.get_filename(), True, part.get_content_charset())
            # else:
            #     attachment = decode_header(part.get_filename(), True, part.get_content_charset())
        name = ''
        for t in part.get_params():
            if t[0] == 'name':
                name = decode_header(t[1], False, part.get_content_charset())
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
            if inline:
                signature = part.get_payload()
        elif content_type == 'application/pgp-keys':
            header = 'PGP-Public-Key: '
            if attachment == '':
                attachment = 'public_key.asc'
        else:
            header = 'Attach: '
            if attachment == '':
                if content_type.find('message/') == 0:
                    attachment = content_type.replace('/', '-') + '.eml'
                else:
                    attachment = 'attachment'
        get_attach(part, part_ls, out, header, attachment)
        return signature

    def decrypt_subject(part, output):  # メッセージ全体が暗号化されていると Subject が事実上空なので付け直す
        protected_headers = False
        for s in part.get_all('Content-Type'):
            if s.find('protected-headers') != -1:
                protected_headers = True
        if not protected_headers:
            return False
        sub = ''
        for s in part.get_all('Subject', ''):
            sub += s
        sub = decode_header(sub, False, part.get_content_charset())
        if sub != '':
            b_v['subject'] = sub
            reset_subject(sub)
            for header in vim.vars['notmuch_show_headers']:
                if header.decode().lower() == 'subject':
                    for i, s in enumerate(output.main['header']):
                        if s.lower().find('subject:'):
                            output.main['header'][i + 1] = 'Subject: ' + sub
                            break
                    break
        return True

    def reset_subject(sub):
        thread_b_v['subject'] = sub
        index = [i for i, x in enumerate(
            THREAD_LISTS[search_term]['list']) if x._msg_id == msg_id][0]
        THREAD_LISTS[search_term]['list'][index].set_subject(sub)
        s = THREAD_LISTS[search_term]['list'][index].get_list(
            not ('list' in THREAD_LISTS[search_term]['sort']))
        thread_b.options['modifiable'] = 1
        thread_b[index] = s
        thread_b.options['modifiable'] = 0

    def get_output(part, part_ls, output):
        def replace_intag(dic, tag, chars, s):  # tag 自身を削除し、それに挟まれた chars を dic の対応に合わせて置換する
            rep_dic = str.maketrans(dic)
            while True:
                re_match = re.search(r'<' + tag + '>' + chars + '</' + tag + '>', s, re.IGNORECASE)
                if re_match is None:
                    break
                match = re_match[0]
                s = s.replace(match, re.sub(r'</?' + tag + '>', r'', match, re.IGNORECASE).translate(rep_dic))
            return s

        content_type = part.get_content_type()
        charset = part.get_content_charset('utf-8')
        # * 下書きメールを単純にファイル保存した時は UTF-8 にしそれをインポート
        # * BASE64 エンコードで情報がなかった時
        # したときのため、仮の値として指定しておく
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
                        output.main['header'].append('Bad-Signature: inline')
                    else:
                        output.main['header'].append('Signature: inline')
                else:
                    output.main['header'].append('Good-Signature: inline')
                set_pgp_result(b_v, thread_b_v, ret)
            # PGP/MIME ではなく本文が暗号化
            elif split[0] == '-----BEGIN PGP MESSAGE-----' and \
                    split[-1] == '-----END PGP MESSAGE-----':
                ret = decrypt_core('gpg', part, 1, output, 'inline')
                if ret.returncode <= 1:  # ret.returncode == 1 は署名検証失敗でも復号化はできている可能性あり
                    tmp_text = ret.stdout.decode(charset)
            if tmp_text != '' and tmp_text != '\n':
                add_content(output.main['content'], tmp_text)
        elif content_type.find('text/html') == 0:
            tmp_text, tmp_tmp = get_mail_context(part, charset, encoding)
            tmp_text = re.sub(r'(<\w[^>]*>)\s+', r' \1',  # 開くタグ直後の空白は前へ移動
                              re.sub(r'\s+(</\w+>)', r'\1 ',  # 閉じるタグ直前の空白は後ろへ移動
                                     tmp_text))
            if tmp_text == '':
                if output.html['part_num']:  # 2 個目以降があれば連番
                    s = 'Del-HTML: index' + str(output.html['part_num']) + '.html'
                else:
                    s = 'Del-HTML: index.html'
                output.main['attach'].append((s, None))
            else:
                # 最適な設定が定まっていない
                html_converter = HTML2Text()
                # html_converter.table_start = True
                if vim.vars.get('notmuch_ignore_tables', 0):
                    html_converter.ignore_tables = True
                tmp_text = replace_intag({  # 上付き添字の変換
                    '0': '⁰', '1': '¹', '2': '²', '3': '³', '4': '⁴',
                    '5': '⁵', '6': '⁶', '7': '⁷', '8': '⁸', '9': '⁹',
                    '+': '⁺', '-': '⁻', '=': '⁼', '(': '⁽', ')': '⁾',
                    'a': 'ª', 'i': 'ⁱ', 'n': 'ⁿ', 'o': 'º'}, 'sup', r'[aino0-9+=()-]+', tmp_text)
                tmp_text = replace_intag({  # 下付き添字の変換
                    '0': '₀', '1': '₁', '2': '₂', '3': '₃', '4': '₄',
                    '5': '₅', '6': '₆', '7': '₇', '8': '₈', '9': '₉',
                    '+': '₊', '-': '₋', '=': '₌', '(': '₍', ')': '₎'}, 'sub', r'[0-9+=()-]+', tmp_text)
                html_converter.body_width = len(tmp_text)
                add_content(
                    output.html['content'],
                    re.sub(r'(?<![A-Za-z]) (?=(_|\*\*))', r'',  # ASCII 外が前後にあると勝手に空白が入る
                           re.sub(r'(_|\*\*) (?![A-Za-z])', r'\1',  # '(?<=(_|\*\*)) (?![A-Za-z])'←エラー
                                  re.sub(r'\s+$', '', re.sub(r'\s+$', '',  # 行末空白削除
                                         re.sub(r'\[\s*\]\([^)]+\)', '',  # リンク文字列がないリンクを削除
                                                re.sub(r'([\n\r]+)\[\s*\]\([^)]+\)\s*[\n\r]', r'\1',
                                                       re.sub(r'!\[\s*\]\([^)]+\)', '',
                                                              re.sub(r'([\n\r]+)!\[\s*\]\([^)]+\)\s*[\n\r]',
                                                                     r'\1',
                                                                     html_converter.handle(tmp_text))))))))))
                if output.html['part_num']:  # 2 個目以降があれば連番
                    s = 'index' + str(output.html['part_num']) + '.html'
                else:
                    s = 'index.html'
                get_attach(part, part_ls, output, 'HTML: ', s)
                # if output[2]:  # 2 個目以降があれば連番
                #     get_attach(part, [part_num], 'HTML: ', 'index'+str(output[2])+'.html')
                # else:
                #     get_attach(part, [part_num], 'HTML: ', 'index.html')
            output.html['part_num'] += 1
        else:
            add_content(output.main['content'],
                        select_header(part, part_ls, False, output))

    def poup_pgp_signature():  # 署名検証に時間がかかるので、その間ポップ・アップを表示したいがうまく行かない←ウィンドウが切り替わった時点で消えるため
        if vim_has('popupwin'):
            vim_popup_atcursor([' Checking signature '], {
                'border': [1, 1, 1, 1],
                'borderchars': ['─', '│', '─', '│', '┌', '┐', '┘', '└'],
                'drag': 1,
                'close': 'click',
                'id': 1024
            })
            # '"minwidth": 400,'+
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
        if type(result) is bytes:
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
            if type(subpart) is list:
                for p in subpart:
                    if p.get_content_type().lower() == 'message/rfc822' \
                            or p.get_content_type().lower() == 'message/rfc2822':
                        return True
        elif c_type == 'message/rfc822' or c_type == 'message/rfc2822':
            subpart = part.get_payload()
            if type(subpart) is list:
                is_delete = False
                for p in subpart:
                    subsub = p.get_payload()
                    if type(subsub) is list:
                        for subp in subsub:
                            is_delete = is_delete or is_delete_rfc(subp)
                    else:
                        is_delete = is_delete or (len(subsub) == 0)
                return is_delete
            else:
                return (len(subpart) == 0)
        return False

    def decrypt_core(cmd, part, decode, out, pgp_info):
        if decode:
            if type(part) is email.message.Message \
                and (part.get_content_type().lower() == 'message/rfc822'
                     or part.get_content_type().lower() == 'message/rfc2822'):
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
            out.main['header'].append('Decrypted: ' + pgp_info)
        if ret.returncode:  # 署名未検証/失敗は ret.returncode >= 1 なので else/elif ではだめ
            if ret.returncode == 1:
                out.main['header'].append('Bad-Signature: ' + pgp_info)
            else:
                out.main['header'].append('Not-Decrypted: ' + pgp_info)
        return ret

    def decrypt(cmd, part, part_ls, out, pgp_info):
        if shutil.which(cmd) is None:
            add_content(out.main['content'],
                        select_header(part, part_ls, True, out))
            pgp_info[0] = ''
            return
        decode = get_part_deocde(part)
        ret = decrypt_core(cmd, part, decode, out, pgp_info[0])
        if ret.returncode <= 1:  # ret.returncode == 1 は署名検証失敗でも復号化はできている可能性あり
            decrypt_msg = email.message_from_string(ret.stdout.decode())
            # ↓本文が UTF-8 そのままだと、BASE64 エンコードされた状態になるので、署名検証に失敗する
            # decrypt_msg = email.message_from_bytes(ret.stdout)
            out.changed_subject = decrypt_subject(decrypt_msg, out)  # シングルパートの Subject 復元
            msg_walk(decrypt_msg, out, part_ls, 2)
        if ret.returncode:  # 署名未検証/失敗は ret.returncode >= 1 なので else/elif ではだめ
            add_content(out.main['content'],
                        select_header(part, part_ls, True, out))
        # add_content(out.main['content'], ret.stdout.decode())

    def msg_walk(msg_file, output, part_ls, flag):
        # flag:   1:ローカルファイル
        #         2:暗号化メール
        def mag_walk_org(part, output, part_ls, flag, pgp_info):
            if flag == 2 and not output.changed_subject:  # マルチパートの Subject 復元
                output.changed_subject = decrypt_subject(part, output)
            part_ls[-1] += 1
            if pgp_info[0] != '':
                decrypt('gpg', part, part_ls, output, ['OpenPGP/MIME ' + pgp_info[0]])
                pgp_info[0] = ''
                return
            content_type = part.get_content_type().lower()
            if content_type == 'application/pgp-signature' \
                    or content_type == 'application/x-pkcs7-signature' \
                    or content_type == 'application/pkcs7-signature':
                return
            # 添付ファイル判定により先にしないと、暗号化部分を添付ファイル扱いとしていないケースに対応できない
            elif content_type == 'message/rfc822' or content_type == 'message/rfc2822':
                select_header(part, part_ls, flag, output)
                part = part.get_payload(0)
                out = Output()
                out.main['header'].append('')
                out.main['header'].append('\f' + content_type + ' part')
                header(part, out, vim.vars['notmuch_show_headers'])
                header(part, out, vim.vars['notmuch_show_hide_headers'])
                header(part, out, ['Encrypt', 'Signature'])
                get_virtual_header(part, out, 'X-Attach')
                get_virtual_header(part, out, 'Attach')
                part_ls[-1] += 1
                msg_walk(part, out, part_ls, 0)
                while True:
                    if output.next is None:
                        output.next = out
                        break
                    output = output.next
            # 添付ファイル判定により先にしないと、暗号化部分を添付ファイル扱いとしていないケースに対応できない
            elif content_type == 'application/pgp-encrypted':
                pgp_info[0], tmp_text = get_mail_context(part, 'utf-8', '')
            elif content_type == 'application/x-pkcs7-mime' \
                    or content_type == 'application/pkcs7-mime':
                decrypt('gpgsm', part, part_ls, output, ['S/MIME'])
            elif content_type == 'message/external-body':
                out = Output()
                msg_walk(part, out, part_ls, 0)
                if out.main['content'] == []:
                    output.main['attach'] += out.main['attach']
                else:
                    out.main['header'] = ['', '\fmessage/external-body part'] \
                        + out.main['header']
                    while True:
                        if output.next is None:
                            output.next = out
                            break
                        output = output.next
            elif part.is_multipart():
                # part_ls[-1] += 1
                msg_walk(part, output, part_ls, flag)
            # if content_type == 'multipart/mixed':
            #     msg_walk(part, output, part_ls, flag)
            # text/plain, html 判定より先にしないと、テキストや HTML ファイルの添付ファイルが本文扱いになる
            elif part.get_content_disposition() == 'attachment':
                #     or part.get('Content-Description', '').find('PGP/MIME') == 0:
                #     ↑ content_type == 'application/pgp-encrypted'
                #        content_type == 'application/pkcs7-mime':
                #  の判定は前にあるので不要
                if flag:
                    part_ls.append(0)
                add_content(output.main['content'],
                            select_header(part, part_ls, False, output))
            else:
                # if content_type.find('text/') != 0:  # なんのためか覚えていない
                #     info.rfc = '\f' + content_type + ' part'
                # else:  # もう使わない
                #     info.rfc = ''
                if flag:
                    part_ls.append(0)
                get_output(part, part_ls, output)
            # info.pre_rfc = info.rfc

        def verify(msg, out, pre, after):
            def sig_part(part, cmd):
                c_type = part.get_content_type().lower()
                if c_type == 'application/pgp-signature':
                    cmd[0] = 'gpg'
                    return True
                elif c_type == 'application/x-pkcs7-signature' \
                        or c_type == 'application/pkcs7-signature':
                    cmd[0] = 'gpgsm'
                    return True
                cmd[0] = ''
                return False

            part0 = msg_file.get_payload(0)
            part1 = msg_file.get_payload(1)
            cmd = ['']
            sig = ''
            verify = ''
            if sig_part(part0, cmd):
                if sig_part(part1, cmd):
                    print_error('Double digital signature.')
                sig = part0
                verify = part1
                ls = copy.copy(pre)
            elif sig_part(part1, cmd):
                verify = part0
                sig = part1
                ls = copy.copy(after)
            else:
                print_error('No exist digital signature.')
            inline = is_inline(verify)
            attachment = decode_header(sig.get_filename(), True, sig.get_content_charset())
            cmd = cmd[0]
            if attachment == '':
                if cmd == 'gpg':
                    attachment = 'signature.asc'
                else:
                    attachment = 'smime.p7s'
            tmp, suffix = os.path.splitext(attachment)
            if suffix == '':
                if cmd == 'gpg':
                    suffix = '.asc'
                else:
                    suffix = 'p7s'
                attachment = tmp + suffix
            if cmd == '' or shutil.which(cmd) is None:
                get_attach(part, ls, out, 'Signature: ', attachment)
                if inline:
                    return sig.get_payload()
                else:
                    return ''
            temp_dir = get_temp_dir()
            make_dir(temp_dir)
            verify_tmp = temp_dir + 'verify.tmp'
            with open(verify_tmp, 'w', newline='\r\n') as fp:  # 改行コードを CR+LF に統一して保存
                fp.write(verify.as_string())
            # pgp_tmp = temp_dir + 'pgp.tmp'
            # write_file(part, 1, pgp_tmp)
            # ユーザ指定すると、gpgsm では鍵がないと不正署名扱いになり、gpg だと存在しないユーザー指定しても、実際には構わず署名としてしまう
            # ret = run([cmd, '--verify', pgp_tmp, verify_tmp], stdout=PIPE, stderr=PIPE)
            ret = run([cmd, '--verify', '-', verify_tmp],
                      input=sig.get_payload(decode=True), stdout=PIPE, stderr=PIPE)
            signature = ''
            if ret.returncode:
                if ret.returncode == 1:
                    header = 'Bad-Signature: '
                else:
                    header = 'Signature: '
                if inline:  # Content-Disposition: inline では電子署名を本文に表示
                    signature = part.get_payload()
            else:
                header = 'Good-Signature: '
            # rm_file_core(pgp_tmp)  # 電子署名なので、直ちに削除する必要はない
            # rm_file_core(verify_tmp)
            set_pgp_result(b_v, thread_b_v, ret)
            get_attach(sig, ls, out, header, attachment)
            return signature

        pgp_info = ['']
        if msg_file.is_multipart():
            pre = copy.copy(part_ls)
            for part in msg_file.get_payload():
                mag_walk_org(part, output, part_ls, flag, pgp_info)
            if msg_file.get_content_type().lower() == 'multipart/signed':
                add_content(output.main['content'],
                            verify(msg_file, output, pre, part_ls))
        else:
            mag_walk_org(msg_file, output, part_ls, flag, pgp_info)
        # if len(output.main['header']) >= 3 and output.main['header'][1][0] == '\f':
        #     output.main['header'][2] += '\u200B'  # メールヘッダ開始

    def print_local_message(output):
        for a in output.main['attach']:
            if not a[1]:
                continue
            a = a[1]
            if a[1] != [-1]:
                continue
            f = a[2] + a[0]
            if os.path.isfile(f) and f.find(PATH + os.sep) == 0:
                out = Output()
                out.main['header'].append('')
                out.main['header'].append('\flocal attachment message part')
                make_header_content(f, out, 1)
                while True:
                    if output.next is None:
                        output.next = out
                        break
                    output = output.next

    def make_header_content(f, output, flag):
        # flag:   1:ローカルファイル
        #         2:暗号化メール
        msg_file = open_email_file(f)
        show_header = vim.vars['notmuch_show_headers']
        hide_header = vim.vars['notmuch_show_hide_headers']
        header(msg_file, output, show_header)
        header(msg_file, output, hide_header)
        for h in [b'Encrypt', b'Signature', b'Fcc']:
            if not (h in show_header) and not (h in hide_header):
                header(msg_file, output, [h])
        get_virtual_header(msg_file, output, 'X-Attach')
        get_virtual_header(msg_file, output, 'Attach')
        part_ls = [1]
        msg_walk(msg_file, output, part_ls, flag)
        # if not flag:
        #     output.main['header'][0] += '\u200B'  # メールヘッダ開始
        print_local_message(output)

    not_search = vim.current.buffer.number
    not_search = s_buf_num('thread', '') == not_search \
        or s_buf_num('show', '') == not_search
    if not_search:
        thread_b = vim.buffers[s_buf_num('thread', '')]
        thread_b_v = thread_b.vars['notmuch']
    else:
        thread_b = vim.buffers[s_buf_num('search', search_term)]
        thread_b_v = thread_b.vars['notmuch']
    # ↓thread から移す方法だと、逆に show で next_unread などを実行して別の search_term の thread に写った場合、その thread でのバッファ変数が書き換わらない
    # subject = thread_b_v['subject']
    # date = thread_b_v['date']
    # tags = thread_b_v['tags']
    if not_search:
        vim.command('MakeShow()')
    else:
        vim.command('MakeView(\'' + vim_escape(search_term) + '\')')
    b = vim.current.buffer
    b_v = b.vars['notmuch']
    b_w = vim.current.window
    if msg_id == '' or (mail_reload is False and msg_id == b_v['msg_id'].decode()):
        b_v['search_term'] = search_term  # 別の検索条件で同じメールを開いていることはあり得るので、search-term の情報だけは必ず更新
        vim_goto_bufwinid(active_win)
        return
    # 以下実際の描画
    msg, f = get_msg()
    if msg is None:
        b_v['msg_id'] = ''
        b_v['subject'] = ''
        b_v['date'] = ''
        b_v['tags'] = ''
        b.options['modifiable'] = 1
        b[:] = ['', 'Already all mail file delete.']
        b.options['modifiable'] = 0
    else:
        vim.options['guitabtooltip'] = 'tags[' + get_msg_tags(msg) + ']'
        # * 添付ファイル名
        # * part番号
        # * 下書きをそのまま送信メールとした時のファイルの保存ディレクトリ
        # vim とやり取りするので辞書のキーは、行番号。item は tuple でなく list
        b_v['attachments'] = {}
        b_v['pgp_result'] = ''
        main_out = Output()
        make_header_content(f, main_out, 0)
        vim_append_content(main_out)
        if check_end_view() and ('unread' in msg.tags):
            msg = change_tags_before_core(msg.messageid)
            with msg.frozen():
                msg.tags.discard('unread')
            change_tags_after_core(msg, True)
    b_name = b.name
    vim.command('silent file! notmuch://show?' + search_term.replace('#', r'\#'))
    vim.command('filter(v:oldfiles, (_, v) => v !~ "^notmuch://")')
    Bwipeout(b_name)
    vim_goto_bufwinid(active_win)
    vim.command('redrawstatus!')


def empty_show():
    b = vim.buffers[s_buf_num('show', '')]
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


def get_msg_id():
    """ notmuch-thread, notmuch-show で Message_ID 取得 """
    b = vim.current.buffer
    b_v = b.vars
    if not ('notmuch' in b_v):  # Notmuch mail-new がいきなり呼び出された時
        return ''
    bufnr = b.number
    b_v = b_v['notmuch']
    s_bufnum = s_buf_num_dic()
    if not ('folders' in s_bufnum):
        # notmuch-folders に対して :bwipeout が実行され、更新された notmuch-edit/draft が有り
        # buf_num['folders'] がない状態になり、notmuch-thread がアクティブだとこの関数が呼ばれることがある
        vim.command('new | only | call s:MakeFoldersList()')
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
    if ('show' in s_bufnum and bufnr == s_bufnum['show']) \
            or (search_term in s_bufnum['view'] and bufnr == s_bufnum['view'][search_term]):
        return b_v['msg_id'].decode()
    elif bufnr == s_bufnum['thread'] \
            or (search_term in s_bufnum['search'] and bufnr == s_bufnum['search'][search_term]):
        if len(THREAD_LISTS[search_term]['list']) < vim.current.window.cursor[0] - 1:
            # メールが削除/移動され、ずれている場合がある
            # メール送信による draft→sent の以降など
            make_thread_core(search_term)
        return THREAD_LISTS[search_term]['list'][vim.current.window.cursor[0] - 1]._msg_id
    return ''


def change_tags_before(msg_id):
    global DBASE
    """ タグ変更の前処理 """
    DBASE = notmuch2.Database(mode=notmuch2.Database.MODE.READ_WRITE)
    return change_tags_before_core(msg_id)


def change_tags_before_core(msg_id):
    global DBASE
    try:
        msg = DBASE.find(msg_id)
    except LookupError:
        print_err('Message-ID: ' + msg_id + ' don\'t find.\nDatabase is broken or emails have been deleted.')
        return None
    return msg


def get_msg_all_tags_list(tmp):
    global DBASE
    """ データベースで使われている全て+notmuch 標準のソート済みタグのリスト """
    DBASE = notmuch2.Database()
    tag = get_msg_all_tags_list_core()
    DBASE.close()
    return tag


def get_msg_all_tags_list_core():
    global DBASE
    tags = list(DBASE.tags)
    tags += ['flagged', 'inbox', 'draft', 'passed', 'replied', 'unread', 'Trash', 'Spam']
    tags = list(set(tags))
    tags = sorted(tags, key=str.lower)
    return tags


def get_msg_tags(msg):
    """ メールのタグ一覧の文字列表現 """
    if msg is None:
        return ''
    emoji_tags = ''
    tags = list(msg.tags)
    for t, emoji in {'unread': '📩', 'draft': '📝', 'flagged': '⭐',
                     'Trash': '🗑', 'attachment': '📎',
                     'encrypted': '🔑', 'signed': '🖋️'}.items():
        if t in tags:
            emoji_tags += emoji
            tags.remove(t)
    return emoji_tags + ' '.join(tags)


def add_msg_tags(tags, adds):
    """ メールのタグ追加→フォルダ・リスト書き換え """
    # try:  # 同一 Message-ID の複数ファイルの移動で起きるエラー対処 (大抵移動は出来ている) エラーの種類不明
    for a in adds:
        tags.add(a)
    # except notmuch.NotInitializedError:
    #     pass


def delete_msg_tags(tags, dels):
    """ メールのタグ削除→フォルダ・リスト書き換え """
    # try:  # 同一 Message-ID の複数ファイルの移動で起きるエラー対処 (大抵移動は出来ている) エラーの種類不明
    for d in dels:
        tags.discard(d)
    # except notmuch.NotInitializedError:
    #     pass


def set_tags(msg_id, s, args):
    """ vim から呼び出しで tag 追加/削除/トグル """
    if args is None:
        return
    tags = args[2:]
    if not tags:
        tags.extend(vim_input_ls('Set tag: ', '', 'customlist,notmuch_py#CompSetTag'))
    if not tags:
        return
    add_tags = []
    delete_tags = []
    toggle_tags = []
    for t in tags:
        if t[0] == '+':
            add_tags.append(t[1:])
        elif t[0] == '-':
            delete_tags.append(t[1:])
        else:
            toggle_tags.append(t)
    if is_draft():
        b_v = vim.current.buffer.vars['notmuch']
        b_tags = b_v['tags'].decode().split(' ')
        for t in add_tags:
            if not (t in b_tags):
                b_tags.append(t)
        for t in delete_tags:
            if t in b_tags:
                b_tags.remove(t)
        for t in toggle_tags:
            if t in b_tags:
                b_tags.remove(t)
            else:
                b_tags.append(t)
        b_v['tags'] = ' '.join(b_tags)
        return
    msg = change_tags_before(msg_id)
    if msg is None:
        return
    msg_tags = []
    for t in msg.tags:
        msg_tags.append(t)
    for tag in toggle_tags:
        if tag in msg_tags:
            if tag not in add_tags:
                delete_tags.append(tag)
        elif tag not in delete_tags:
            add_tags.append(tag)
    with msg.frozen():
        delete_msg_tags(msg.tags, delete_tags)
        add_msg_tags(msg.tags, add_tags)
    change_tags_after(msg, True)
    return [0, 0] + tags


def add_tags(msg_id, s, args):
    """ vim から呼び出しで tag 追加 """
    if args is None:
        return
    tags = args[2:]
    if not tags:
        tags.extend(vim_input_ls('Add tag: ', '', 'customlist,notmuch_py#CompAddTag'))
    if not tags:
        return
    if is_draft():
        b = vim.current.buffer
        b_v = b.vars['notmuch']
        b_tags = b_v['tags'].decode().split(' ')
        for t in tags:
            if not (t in b_tags):
                b_tags.append(t)
        b_v['tags'] = ' '.join(b_tags)
        b.options['modified'] = 1
        return
    msg = change_tags_before(msg_id)
    if msg is None:
        return
    with msg.frozen():
        add_msg_tags(msg.tags, tags)
    change_tags_after(msg, True)
    return [0, 0] + tags


def delete_tags(msg_id, s, args):
    """ vim から呼び出しで tag 削除 """
    if args is None:
        return
    tags = args[2:]
    if not tags:
        tags.extend(vim_input_ls('Delete tag: ', '', 'customlist,notmuch_py#CompDelTag'))
    if not tags:
        return
    if is_draft():
        b = vim.current.buffer
        b_v = b.vars['notmuch']
        b_tags = b_v['tags'].decode().split(' ')
        for t in tags:
            if t in b_tags:
                b_tags.remove(t)
        b_v['tags'] = ' '.join(b_tags)
        b.options['modified'] = 1
        return
    msg = change_tags_before(msg_id)
    if msg is None:
        return
    with msg.frozen():
        delete_msg_tags(msg.tags, tags)
    change_tags_after(msg, True)
    return [0, 0] + tags


def toggle_tags(msg_id, s, args):
    """ vim からの呼び出しで tag をトグル """
    if args is None:
        return
    tags = args[2:]
    if not tags:
        tags.extend(vim_input_ls('Toggle tag: ', '', 'customlist,notmuch_py#CompTag'))
    if not tags:
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
        msg_tags = []
        for t in msg.tags:
            msg_tags.append(t)
        with msg.frozen():
            for tag in tags:
                if tag in msg_tags:
                    msg.tags.discard(tag)
                else:
                    msg.tags.add(tag)
        change_tags_after(msg, True)
    return [0, 0] + tags


def get_msg_tags_list(tmp):
    global DBASE
    """ vim からの呼び出しでメールのタグをリストで取得 """
    msg_id = get_msg_id()
    if msg_id == '':
        return []
    if is_draft():
        tags = vim.current.buffer.vars['notmuch']['tags'].decode().split(' ')
    else:
        DBASE = notmuch2.Database()
        msg = DBASE.find(msg_id)
        tags = []
        for tag in msg.tags:
            tags.append(tag)
        DBASE.close()
    return sorted(tags, key=str.lower)


def get_msg_tags_any_kind(tmp):
    global DBASE
    """ メールに含まれていないタグ取得には +を前置、含まれうタグには - を前置したリスト """
    msg_id = get_msg_id()
    if msg_id == '':
        return []
    DBASE = notmuch2.Database()
    tags = get_msg_all_tags_list_core()
    if is_draft():
        msg_tags = vim.current.buffer.vars['notmuch']['tags'].decode().split(' ')
    else:
        msg = DBASE.find(msg_id)
        msg_tags = []
        for t in msg.tags:
            msg_tags.append(t)
    DBASE.close()
    add_tags = []
    for t in tags:
        if t not in msg_tags:
            add_tags.append('+' + t)
    for t in msg_tags:
        tags.append('-' + t)
    return sorted(tags + add_tags, key=str.lower)


def get_msg_tags_diff(tmp):
    global DBASE
    """ メールに含まれていないタグ取得 """
    msg_id = get_msg_id()
    if msg_id == '':
        return []
    DBASE = notmuch2.Database()
    tags = get_msg_all_tags_list_core()
    if is_draft():
        for t in vim.current.buffer.vars['notmuch']['tags'].decode().split(' '):
            tags.remove(t)
    else:
        msg = DBASE.find(msg_id)
        for tag in msg.tags:
            tags.remove(tag)
    DBASE.close()
    return sorted(tags, key=str.lower)


def get_search_snippet(word):
    """ word によって補完候補を切り替える """
    def get_address(s):
        return run(['notmuch', 'address', '--deduplicate=address', s],
                   stdout=PIPE, stderr=PIPE).stdout.splitlines()

    if word[0:7] == 'folder:':
        snippet = ['folder:' + v + ' '
                   for v in get_mail_folders()]
    elif word[0:4] == 'tag:':
        snippet = ['tag:' + v + ' '
                   for v in get_msg_all_tags_list('')]
    elif word[0:5] == 'from:':
        snippet = ['from:' + email2only_address(v.decode()) + ' '
                   for v in get_address('from:')]
    elif word[0:3] == 'to:':
        snippet = ['to:' + email2only_address(v.decode()) + ' '
                   for v in get_address('to:')]
    else:
        return ['attachment:', 'body:', 'date:', 'folder:', 'from:', 'id:',
                'lastmod:', 'mimetype:', 'path:', 'property:', 'query:',
                'subject:', 'tag:', 'thread:', 'to:']
    snippet.sort(key=str.lower)
    return snippet


def change_tags_after(msg, change_b_tags):
    global DBASE
    """ 追加/削除した時の後始末 """
    # change_b_tags: thread, show の b:tags を書き換えるか?
    # ↑インポート、送信時は書き換え不要
    change_tags_after_core(msg, change_b_tags)
    DBASE.close()


def change_tags_after_core(msg, change_b_tags):
    """ Post-processing after tag change

    canage
      * buffer variables using statusline
      * icons of tag in thread list
      * folder list information
    """
    msg.tags.to_maildir_flags()
    if change_b_tags:
        msg_id = msg.messageid
        tags = get_msg_tags(msg)
        ls_tags = list(msg.tags)
        for b in vim.buffers:
            if not ('notmuch' in b.vars):
                continue
            b_v = b.vars['notmuch']
            if not ('msg_id' in b_v):
                continue
            b_msgid = b_v['msg_id'].decode()
            if b_msgid == '':
                continue
            b_num = b.number
            buf_num = s_buf_num_dic()
            b_show = buf_num['show']
            b_view = buf_num['view'].values()
            b_thread = buf_num['thread']
            b_search = buf_num['search'].values()
            if (b_num == b_show or (b_num in b_view)
                or b_num == b_thread or (b_num in b_search)) \
                    and msg_id == b_msgid:
                b_v['tags'] = tags
                # print(b_num, tags)
            if b_num == b_thread or b_num in b_search:
                search_term = b_v['search_term'].decode()
                if search_term == '':
                    continue
                line = [i for i, msg in enumerate(
                    THREAD_LISTS[search_term]['list']) if msg._msg_id == msg_id]
                if not line:
                    continue
                line = line[0]
                msg = THREAD_LISTS[search_term]['list'][line]
                msg._tags = ls_tags
                b.options['modifiable'] = 1
                b[line] = msg.get_list(not ('list' in THREAD_LISTS[search_term]['sort']))
                b.options['modifiable'] = 0
                reset_cursor_position(b, line + 1)
    reprint_folder()


def reset_cursor_position(b, line):
    """ thread でタグ絵文字の後にカーソルを置く """
    s = b[line - 1]
    if s == '':
        return
    b_num = b.number
    for t in vim.tabpages:
        t_num = t.number
        for i in [i for i, x in enumerate(list(
                vim_tabpagebuflist(t_num))) if x == b_num]:
            w = t.windows[i]
            w.cursor = (line, len(s[:re.match(r'^[^\t]+', s).end()].encode()) + 1)
            # vim_win_execute(vim_win_getid(w.number, t_num), 'redraw')  # ←カーソル移動しても点滅する描画位置が行頭になる時が有る対策


def unread_before(active_win):
    """ 未読メールを探すときの前処理 (previos_unread(), next_unread() の共通部分) """
    active_win = int(active_win)
    if not ('search_term' in vim.current.buffer.vars['notmuch']):
        if active_win == s_buf_num('folders', ''):
            msg_id = ''
            if not ('thread' in s_buf_num_dic()):
                vim.command('MakeThreadList()')
            active_win = s_buf_num('thread', '')
            search_term = vim.vars['notmuch_folders'][vim.current.window.cursor[0] - 1][1]
        else:
            msg_id = get_msg_id()
            search_term = vim.vars['notmuch_folders'][0][1]
    else:
        msg_id = get_msg_id()
        search_term = vim.current.buffer.vars['notmuch']['search_term']
    search_term = search_term.decode()
    if is_same_tabpage('search', search_term) or is_same_tabpage('view', search_term):
        search_view = True  # 検索スレッドや検索ビューや否かのフラグ
    else:
        search_view = False
    if search_view:
        b_num = s_buf_num('search', search_term)
    else:
        b_num = s_buf_num('thread', '')
    for b in vim.buffers:
        if b.number == b_num:
            v_thread = b.vars['notmuch']
            break
    v_thread['running_open_mail'] = True
    return active_win, msg_id, search_term, search_view, v_thread


def search_and_open_unread(active_win, index, search_term, v, top):
    ''' search_term の検索方法で未読が有れば、そのスレッド/メールを開く
    v: thread window vlues
    top: 0/-1 => view top/last mail
    '''
    if type(search_term) is bytes:
        search_term = search_term.decode()
    if search_term == '' \
            or not DBASE.count_messages('(' + search_term + ') and tag:unread'):
        vim_goto_bufwinid(active_win)
        return False
    b_num = s_buf_num('folders', '')
    for t in vim.tabpages:
        for i in [i for i, x in enumerate(list(
                vim_tabpagebuflist(t.number))) if x == b_num]:
            t.windows[i].cursor = (index + 1, 0)  # ここまではフォルダ・リストの順番としてindex使用
    b_num = s_buf_num('thread', '')
    print_thread_core(b_num, search_term, False, False)
    # ここからはスレッド・リストの順番としてindex使用
    index = get_unread_in_THREAD_LISTS(search_term)
    if not index:  # 作成済み THREAD_LISTS[search_term] には未読メールがない→作成後にメール受信
        print_thread_core(b_num, search_term, False, True)
        index = get_unread_in_THREAD_LISTS(search_term)
    index = index[top]
    reset_cursor_position(vim.current.buffer, index + 1)
    fold_open()
    change_buffer_vars_core()
    if is_same_tabpage('show', '') or is_same_tabpage('view', search_term):
        open_mail_by_msgid(search_term,
                           THREAD_LISTS[search_term]['list'][index]._msg_id,
                           active_win, False)
    if s_buf_num('folders', '') == active_win:
        vim_goto_bufwinid(s_buf_num('thread', ''))
    else:
        vim_goto_bufwinid(active_win)
    DBASE.close()
    v['running_open_mail'] = False
    return True


def open_mail_by_buf_kind_index(w, k, s, index, v):
    """ 同一スレッド内の未読メール """
    goto_winid = vim_goto_bufwinid(s_buf_num(k, s if k == 'search' else ''))
    reset_cursor_position(vim.current.buffer, index + 1)
    if goto_winid:
        change_buffer_vars_core()
        fold_open()
    if is_same_tabpage('show', '') or is_same_tabpage('view', s):
        open_mail_by_msgid(s, THREAD_LISTS[s]['list'][index]._msg_id, w, False)
    DBASE.close()
    v['running_open_mail'] = False


def get_serach_term(search_term, folders):
    """ search_term が folders の何番目か?
    search_term が空なら一つ前の扱いに書き換える
    """
    for index, folder_way in enumerate(folders):
        if search_term == folder_way[1].decode():
            if search_term == '':
                index -= 1
                search_term = folders[index][1].decode()
            break
    return search_term, index


def next_unread(active_win):
    """ 次の未読メッセージが有れば移動(表示した時全体を表示していれば既読になるがそれは戻せない) """
    global DBASE
    active_win, msg_id, search_term, search_view, v_thread = unread_before(active_win)
    # タグを変更することが有るので、書き込み権限も
    DBASE = notmuch2.Database(mode=notmuch2.Database.MODE.READ_WRITE)
    if msg_id == '':  # 空のメール/スレッド、notmuch_folders から実行された場合
        # if search_view:  # そもそも検索にヒットしなければ、search, view は開かれないはず
        #     vim_goto_bufwinid(active_win)
        #     v_thread['running_open_mail'] = False
        #     return
        if vim_goto_bufwinid(s_buf_num("thread", '')) == 0:
            reopen('thread', search_term)
        folders = vim.vars['notmuch_folders']
        search_term, index = get_serach_term(search_term, folders)
        for folder_way in folders[index:]:  # search_term 以降で未読が有るか?
            if search_and_open_unread(active_win, index, folder_way[1], v_thread, 0):
                return
            index = index + 1
        for index, folder_way in enumerate(folders):  # 見つからなかったので最初から
            if search_and_open_unread(active_win, index, folder_way[1], v_thread, 0):
                return
        vim_goto_bufwinid(active_win)
        DBASE.close()
        v_thread['running_open_mail'] = False
        return
    index = [i for i, x in enumerate(
        THREAD_LISTS[search_term]['list']) if x._msg_id == msg_id][0]
    indexes = get_unread_in_THREAD_LISTS(search_term)
    # ↑ len(indexes) > 0 なら未読有り
    index = [i for i, i in enumerate(indexes) if i > index]
    if index:  # 未読メールが同一スレッド内の後ろに有る
        open_mail_by_buf_kind_index(active_win,
                                    'search' if search_view else 'thread',
                                    search_term, index[0], v_thread)
        return
    # else:  # 同一スレッド内に未読メールが有っても後ろには無い
    #     pass
    # else:  # 同一スレッド内に未読がない、
    #     pass
    # 同一スレッド内に未読がない、または同一スレッド内に未読メールが有っても後ろには無い
    if search_view:  # search, view では先頭の未読に移動
        if indexes:
            open_mail_by_buf_kind_index(active_win, 'search', search_term, indexes[0], v_thread)
        return
    folders = vim.vars['notmuch_folders']
    for index, folder_way in enumerate(folders):  # 同一検索方法までスキップ
        if search_term == folder_way[1].decode():
            break
    if index < len(folders):
        next_index = index + 1  # 現在開いている検索条件の次から未読が有るか? を調べるのでカウント・アップ
        for folder_way in folders[next_index:]:
            if search_and_open_unread(active_win, next_index, folder_way[1], v_thread, 0):
                return
            next_index += 1
    # フォルダ・リストの最初から未読が有るか? を探し直す
    for index_refirst, folder_way in enumerate(folders[:index + 1]):
        if search_and_open_unread(active_win, index_refirst, folder_way[1], v_thread, 0):
            return
    DBASE.close()
    v_thread['running_open_mail'] = False


def previous_unread(active_win):
    """ 前の未読メッセージが有れば移動(表示した時全体を表示していれば既読になるがそれは戻せない) """
    def search_previos_unread(index):
        ret = False
        count_folder = len(folders)
        while True:
            index = (index + count_folder - 1) % count_folder
            f_search_term = folders[index][1].decode()
            if search_term == f_search_term:
                break
            if search_and_open_unread(active_win, index, f_search_term, v_thread, -1):
                ret = True
                break
        DBASE.close()
        v_thread['running_open_mail'] = False
        return ret

    global DBASE
    # タグを変更することが有るので、書き込み権限も
    DBASE = notmuch2.Database(mode=notmuch2.Database.MODE.READ_WRITE)
    active_win, msg_id, search_term, search_view, v_thread = unread_before(active_win)
    folders = vim.vars['notmuch_folders']
    if msg_id == '':  # 空のメール/スレッド、notmuch_folders から実行された場合
        if vim_goto_bufwinid(s_buf_num("thread", '')) == 0:
            reopen('thread', search_term)
        search_term, index = get_serach_term(search_term, folders)
        if search_and_open_unread(active_win, index, search_term, v_thread, -1):  # 該当 search_term に未読あり
            return
        search_previos_unread(index)
        return
    index = [i for i, x in enumerate(
        THREAD_LISTS[search_term]['list']) if x._msg_id == msg_id][0]
    indexes = get_unread_in_THREAD_LISTS(search_term)
    # ↑ len(indexes) > 0 なら未読有り
    index = [i for i, i in enumerate(indexes) if i < index]
    if index:  # 未読メールが同一スレッド内の前に有る
        open_mail_by_buf_kind_index(active_win,
                                    'search' if search_view else 'thread',
                                    search_term, index[-1], v_thread)
        return
    search_term, index = get_serach_term(search_term, folders)
    if search_previos_unread(index):
        return
    if indexes:
        open_mail_by_buf_kind_index(active_win,
                                    'search' if search_view else 'thread',
                                    search_term, indexes[-1], v_thread)
        return
    DBASE.close()
    v_thread['running_open_mail'] = False


def reindex_mail(msg_id, s, args):
    shellcmd_popen(['notmuch', 'reindex', 'id:"' + msg_id + '"'])
    return [0, 0]  # ダミー・リストを返す


def decode_header(s, is_file, chrset):
    if s is None:
        return ''
    name = ''
    for string, charset in email.header.decode_header(s):
        if charset is None:
            if type(string) is bytes:
                name += string.decode('raw_unicode_escape')
            elif string.find("\x1B") != -1 and chrset is not None:  # デコードされていない生 JIS のままなど
                name += string.encode(chrset).decode(chrset)
            else:  # デコードされず bytes 型でないのでそのまま
                name += string
        elif charset == 'unknown-8bit':
            name += string.decode('utf-8')
        else:
            try:
                name += string.decode(charset)
            except UnicodeDecodeError:  # コード外範囲の文字が有る時のエラー
                charset = replace_charset(charset)  # iso-2022-jp-3, gb18030 へ置き換え再度試みる
                try:
                    name += string.decode(charset)
                except UnicodeDecodeError:
                    if is_file:
                        print_warring('File name has out-of-code range characters.')
                    else:
                        print_warring('Header has out-of-code range characters.')
                    name += decode_string(string, charset, 'backslashreplace')
            except Exception:
                name += string.decode('raw_unicode_escape')
    return re.sub('[\u200B-\u200D\uFEFF]', '', name.replace('\n', ' '))  # ゼロ幅文字削除


def get_part_deocde(part):
    # 添付ファイルでも Context-Type='text/plain' 等のテキストで、Content-Transfer-Encoding=8bit なら取り出し時にデコードの必要なし
    transfer_encoding = part.get('Content-Transfer-Encoding')
    if transfer_encoding is None:
        return 1
    else:
        mime = part.get_content_type().lower()
        if (mime == 'message/rfc822' or mime == 'message/rfc2822'):
            # message/rfc822 を想定しているが、他や 7bit のケースが有るかは未確認
            return 2
        elif transfer_encoding.lower() != '8bit':
            return 1
        elif mime.find('text') == 0:
            return 0
        else:
            print_err('Error Context-Type: ' + part.get_content_type() + ', ' + transfer_encoding)
            return -1


def get_attach_info(line):
    def same_name():
        # バッファの行番号毎に同一ファイル名の出現順序を返す
        line_name = {}  # 行番号とファイル名取得
        for i, j in b_attachments.items():
            name = j[0].decode('utf-8')
            i = i.decode()
            if j[0] == '':
                name = 'noname'
            line_name[i] = name
        line_name_sorted = {}  # 行番号とファイル名を行番号順にソート
        for i in sorted(line_name.keys(), key=int):
            line_name_sorted[i] = line_name[i]
        line_count = {}
        name_count = {}
        for i, j in line_name_sorted.items():
            if j in name_count:
                name_count[j] += 1
            else:
                name_count[j] = 0
            line_count[i] = name_count[j]
        return line_count

    global DBASE
    b_v = vim.current.buffer.vars['notmuch']
    try:
        search_term = b_v['search_term'].decode()
    except KeyError:
        return None, None, None, None
    bufnr = vim.current.buffer.number
    if bufnr != s_buf_num('show', '') \
            and (not (search_term in s_buf_num('view', ''))
                 or bufnr != s_buf_num('view', search_term)):
        return None, None, None, None
    line = str(line)
    b_attachments = b_v['attachments']
    if line not in b_attachments:
        return None, None, None, None
    name, part_num, dirORmes_str = b_attachments[line]
    name = name.decode('utf-8')
    if name == '':  # 元々ファイル名情報がない場合
        name = 'noname'
    part_num = [i for i in part_num]
    if part_num == [-1]:
        return name, None, None, dirORmes_str.decode('utf-8')
    tmpdir = get_attach_dir() + sha256(b_v['msg_id']).hexdigest() + os.sep
    count = same_name()
    if count[line]:
        name = os.path.splitext(name)[0] + '-' + str(count[line]) + os.path.splitext(name)[1]
    if len(part_num) >= 2:
        dirORmes_str = email.message_from_bytes(dirORmes_str)
        decode = get_part_deocde(dirORmes_str)
        return name, dirORmes_str, decode, tmpdir
    msg_id = b_v['msg_id'].decode()
    DBASE = notmuch2.Database()
    msg = get_message('(' + search_term + ') id:"' + msg_id + '"')
    if msg is None:  # 同一条件+Message_ID で見つからなくなっているので Message_ID だけで検索
        print('Already Delete/Move/Change folder/tag')
        msg = DBASE.find(msg_id)
    with open(msg.path, 'rb') as fp:
        msg_file = email.message_from_binary_file(fp)
    DBASE.close()
    part_count = 1
    part_num = part_num[0]
    for attach in msg_file.walk():
        # if attach.get_content_type().lower() != 'message/rfc822' \
        #         and attach.get_content_type().lower() != 'message/rfc2822' \
        #         and attach.is_multipart():
        #     continue
        if part_num == part_count:
            break
        part_count += 1
    decode = get_part_deocde(attach)
    if decode < 0:
        return None, None, None, None
    return name, attach, decode, tmpdir


def open_attachment(args):
    """ vim で Attach/HTML: ヘッダのカーソル位置の添付ファイルを開く """
    def same_attach(fname):
        fname = fname.decode('utf-8')
        for i, ls in vim.current.buffer.vars['notmuch']['attachments'].items():
            name = ls[0].decode('utf-8')
            if fname == name:
                return get_attach_info(i.decode())
        return None, None, None, None

    args = [int(s) for s in args]
    for i in range(args[0], args[1] + 1):
        close_top = vim.bindeval('foldclosed(".")')
        if close_top != -1:
            vim.command('normal! zo')
            vim.current.window.cursor = (close_top, 0)
            return
        filename, attachment, decode, full_path = get_attach_info(i)
        if filename is None:
            filename, attachment, decode, full_path = same_attach(vim.bindeval('expand("<cfile>>")'))
            if filename is None:
                syntax = vim.bindeval('synIDattr(synID(line("."), col("."), 1), "name")')
                if vim_foldlevel('.') >= 3 \
                        or syntax == b'mailHeader' \
                        or syntax == b'mailHeaderKey' \
                        or syntax == b'mailNewPartHead' \
                        or syntax == b'mailNewPart':
                    vim.command('normal! za')
                elif 'open' in vim.vars['notmuch_open_way']:
                    if syntax != 'mailHeaderEmail' and \
                            (syntax.decode().find('mailHeader') == 0 or syntax == 'mailSubject'):
                        return
                    vim.command(vim.vars['notmuch_open_way']['open'].decode())
                return
        if attachment is not None or decode is not None:
            if not os.path.isdir(full_path):
                os.makedirs(full_path)
                os.chmod(full_path, 0o700)
        elif full_path == '':  # attachment, decode が None
            # +保存ディレクトリが空なら送信メールでなくメール本文を単純にテキスト・ファイルとして保存し、それをインポートしたファイル
            print_warring('The header is virtual.')
            return
        full_path += filename
        if not os.path.isfile(full_path):
            write_file(attachment, decode, full_path)
        print('open ' + filename)
        try:
            ret = run([vim.vars['notmuch_view_attachment'].decode(),
                      full_path], stdout=PIPE, stderr=PIPE, timeout=0.5)
            # timeout の指定がないと、アプリによって終了待ちになる
            if ret.returncode:
                print_warring(ret.stderr.decode('utf-8'))
        except TimeoutExpired:
            pass


def get_top(part, i):
    """ multipart の最初の情報を取得したいときチェック用 """
    t = type(part)
    if t == bytes:
        part = part.decode('utf-8', 'replace')
    elif t == email.message.Message:
        part = part.as_string()
    if type(part) is str:
        s = re.sub(r'\r\n', r'\n', re.sub(r'\r', r'\n', part))
        match = re.search(r'\n\n', s)
        if match is not None:
            s = s[match.start() + 2:]
        print(s.split('\n')[0])
        if len(s) >= i:
            s = s[:i]
        print('')
        print('\n'.join(s))
    else:
        print(type(part), part)


def write_file(part, decode, save_path):
    """ 添付ファイルを save_path に保存 """
    def get_html_charset(part):  # text/html なら HTML の charset を取得する
        html = part.get_content_type()
        if html is None:
            return ''
        elif html.lower() != 'text/html':
            return ''
        else:
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
        charset = replace_charset(part.get_content_charset('utf-8'))
        # * 下書きメールを単純にファイル保存した時は UTF-8 にしそれをインポート
        # * BASE64 エンコードで情報がなかった時
        # したときのため、仮の値として指定しておく
        try:
            part = codecs.decode(part.get_payload(decode=True), encoding=charset)
            html = replace_charset(html)
            with open(save_path, 'wb') as fp:
                fp.write(codecs.encode(part, encoding=html))
        except UnicodeDecodeError:  # iso-2022-jp で JIS 外文字が使われていた時
            # ↓全てをこの decode=False で行うと quoted-printable に対応できない
            part = part.get_payload(decode=False)
            with open(save_path, 'wb') as fp:
                fp.write(codecs.encode(part))
    elif decode:
        if type(part) is email.message.Message \
                and (part.get_content_type().lower() == 'message/rfc822'
                     or part.get_content_type().lower() == 'message/rfc2822'):
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


def save_attachment(args):
    """ vim で Attach/HTML: ヘッダのカーソル位置の添付ファイルを保存 """
    print('')  # もし print_warning を出していればそれを消す
    args = [int(s) for s in args[0:2]]
    for i in range(args[0], args[1] + 1):
        filename, attachment, decode, full_path = get_attach_info(i)
        if filename is None:
            return
        elif attachment is None and decode is None:  # attachment, decode が None
            # →インポート/送信メールどちらであれ仮想ヘッダ添付ファイルの保存は意味がない
            print_warring('The header is virtual.')
            return
        save_path = get_save_filename(get_save_dir() + filename)
        if save_path == '':
            return
        make_dir(os.path.dirname(save_path))
        # 添付ファイルを開く時の一時的ディレクトリ full_path に同じファイルが有るか? 調べ、有ればそれを移動
        full_path += filename
        if os.path.isfile(full_path):
            shutil.move(full_path, save_path)
        else:
            write_file(attachment, decode, save_path)
        vim.command('redraw')
        print('save ' + save_path)


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
        c_header = 'message/external-body; access-type=x-mutt-deleted;\n' \
            + '\texpiration="' + m_time + '"; length=' \
            + str(len(s))
        part.__setitem__('Content-Type', c_header)
        part.set_payload(header)
        return True

    def delete_attachment_in_show(args):
        def delete_attachment_only_part(fname, part_num):  # part_num 番目の添付ファイルを削除
            with open(fname, 'r') as fp:
                msg_file = email.message_from_file(fp)
            i = 1
            for part in msg_file.walk():
                # if part.is_multipart() \
                #         and part.get_content_type().lower() != 'message/rfc822' \
                #         and part.get_content_type().lower() != 'message/rfc2822':
                #     i += 1
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
        # メール本文表示だと未読→既読扱いでタグを変更することが有るので書き込み権限も
        DBASE = notmuch2.Database(mode=notmuch2.Database.MODE.READ_WRITE)
        args = [int(s) for s in args[0:2]]
        deleted_attach = []  # 実際に削除する添付ファイルが書かれた行番号
        b_attachments = b_v['attachments']
        b.options['modifiable'] = 1
        # 実際の添付ファイル削除処理
        for i in range(args[1], args[0] - 1, -1):  # 削除すると part_num がずれるので後ろから削除
            line = str(i)
            if line in b_attachments:
                tmp_name, part_num, tmpdir = b_attachments[line]
                part_num = [i for i in part_num]
                if part_num == [-1]:
                    print_warring('The header is virtual.')
                elif len(part_num) >= 2:
                    print_warring('Can not delete:  Encrypted/Local.')
                else:
                    del b_attachments[line]
                    line = int(line)
                    deleted_attach.append(line)
                    line -= 1
                    if b[line].find('HTML:') == 0 and '\fHTML part' not in b[:]:
                        # HTML パートで text/plain が無ければ削除しない
                        print_warring('The mail is only HTML.')
                    else:
                        if b[line].find('HTML:') == 0:
                            for i, b_i in enumerate(b):
                                if b_i == '\fHTML part':
                                    break
                            b[i:] = None
                        b[line] = 'Del-' + b[line]
                        msg = DBASE.find(msg_id)
                        for f in msg.filenames():
                            delete_attachment_only_part(f, part_num[0])
        b.options['modifiable'] = 0
        # 削除した添付ファイルに合わせて他の行の添付ファイルの情報 (part_num) 更新
        for k, v in b_attachments.items():
            slide = len([j for j in deleted_attach if j < int(k)])
            part_num = [i for i in v[1]]
            if slide and part_num != [-1] and len(part_num) == 1:
                v[1] = [part_num[0] + slide]
                # 削除ファイルの情報を multipart で書き込むので、part_num としては増える
        DBASE.close()

    def delete_attachment_in_thread(args, search_term):
        # メール本文表示だと未読→既読扱いでタグを変更することが有るので書き込み権限も
        def delete_attachment_all(fname):  # text/plain, text/html 以外の全て添付ファイルを削除
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
                if part.is_multipart() \
                        and part.get_content_type().lower() != 'message/rfc822' \
                        and part.get_content_type().lower() != 'message/rfc2822':
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

        DBASE = notmuch2.Database(mode=notmuch2.Database.MODE.READ_WRITE)
        args = [int(s) for s in args[0:2]]
        for i in range(args[0], args[1] + 1):
            msg_id = THREAD_LISTS[search_term]['list'][i - 1]._msg_id
            msg = DBASE.find(msg_id)
            for f in msg.filenames():
                delete_attachment_all(f)
        DBASE.close()
        bnum = vim.current.buffer.number
        if bnum == s_buf_num('thread', '') \
                and is_same_tabpage('show', ''):
            b = vim.buffers[s_buf_num('show', '')]
        elif bnum == s_buf_num('search', search_term) \
                and is_same_tabpage('view', search_term):
            b = vim.buffers[s_buf_num('view', search_term)]
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
            print_warring('Don\'t delete: Encrypted/Local/Virtual!')

    import time
    global DBASE
    b = vim.current.buffer
    bufnr = b.number
    b_v = b.vars['notmuch']
    search_term = b_v['search_term'].decode()
    if bufnr == s_buf_num('show', '') \
        or ((search_term in s_buf_num('view', ''))
            and bufnr == s_buf_num('view', search_term)):
        delete_attachment_in_show(args)
    elif bufnr == s_buf_num('thread', '') \
        or ((search_term in s_buf_num('search', ''))
            and bufnr == s_buf_num('search', search_term)):
        delete_attachment_in_thread(args, search_term)


def cut_thread(msg_id, dumy):
    if msg_id == '':
        msg_id = get_msg_id()
        if msg_id == '':
            return
    bufnr = vim.current.buffer.number
    if bufnr == s_buf_num('folders', ''):
        return
    db = notmuch2.Database()
    msg = db.find(msg_id)
    changed = False
    for f in msg.filenames():
        with open(f, 'r') as fp:
            msg_file = email.message_from_file(fp)
        in_reply = get_msg_header(msg_file, 'In-Reply-To')
        if in_reply == '':
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
    db.close()
    if changed:
        shellcmd_popen(['notmuch', 'reindex', 'id:"' + msg_id + '"'])
        search_term = vim.current.buffer.vars['notmuch']['search_term'].decode()
        print_thread(bufnr, search_term, False, True)
        index = [i for i, x in enumerate(
            THREAD_LISTS[search_term]['list']) if x._msg_id == msg_id]
        if index:
            reset_cursor_position(vim.current.buffer, index[0] + 1)
            fold_open()
        else:
            print('Already Delete/Move/Change folder/tag')


def connect_thread_tree():
    r_msg_id = get_msg_id()
    if r_msg_id == '':
        return
    bufnr = vim.current.buffer
    search_term = bufnr.vars['notmuch']['search_term'].decode()
    bufnr = bufnr.number
    if bufnr != s_buf_num('thread', '') \
            and not (search_term in s_buf_num('search', '')) \
            and bufnr != s_buf_num('search', search_term):
        print_warring('The command can only be used on thread/search.')
        return
    lines = get_mark_in_thread()
    if lines == []:
        print_warring('Mark the email that you want To connect. (:Notmuch mark)')
        return
    db = notmuch2.Database()
    for line in lines:
        msg_id = THREAD_LISTS[search_term]['list'][line]._msg_id
        if r_msg_id == msg_id:
            continue
        msg = db.find(msg_id)
        for f in msg.filenames():
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
    db.close()
    print_thread(bufnr, search_term, False, True)
    index = [i for i, x in enumerate(
        THREAD_LISTS[search_term]['list']) if x._msg_id == r_msg_id]
    if index:
        reset_cursor_position(vim.current.buffer, index[0] + 1)
        fold_open()
    else:
        print('Already Delete/Move/Change folder/tag')


def get_mark_in_thread():
    """ マークの付いた先頭行を 0 とした行番号リストを返す """
    lines = []
    # notmuch-thread と notmuch-search からしか呼ばれないので、bufnr() を調べない
    signs = vim.bindeval('sign_getplaced(' + str(vim.current.buffer.number)
                         + ', {"name": "notmuch", "group": "mark_thread"})')[0]['signs']
    for i in range(len(signs)):
        lines.append(signs[i]['lnum'] - 1)
    return lines


def get_save_dir():
    if 'notmuch_save_dir' in vim.vars:
        # 設定が有れば ~ や $HOME などの環境変数展開
        return os.path.expandvars(
            os.path.expanduser(vim.vars['notmuch_save_dir'].decode())) + os.sep
    else:
        return os.getcwd() + os.sep


def get_save_filename(path):
    """ 保存ファイル名の取得 (既存ファイルなら上書き確認) """
    while True:
        if use_browse():
            path = vim_browse(1, 'Save', os.path.dirname(path), os.path.basename(path)).decode()
        else:
            path = vim_input('Save as: ', path, 'file')
        path = os.path.expandvars(os.path.expanduser(path))
        if path == '':
            return ''
        elif os.path.isfile(path):
            if is_gtk():
                over_write = vim_confirm('Overwrite?', 'Yes(&Y)\nNo(&N)', 1, 'Question')
            else:
                over_write = vim_confirm('Overwrite?', '&Yes\n&No', 1, 'Question')
            if over_write == 1:
                return path
        elif os.path.isdir(path):
            print_warring('\'' + path + '\' is directory.')
        else:
            return path


def view_mail_info():
    """ メール情報表示 """
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
                lists += ['Modified   : '
                          + datetime.datetime.fromtimestamp(os.path.getmtime(f)).strftime(DATE_FORMAT),
                          'Size       : ' + str(os.path.getsize(f)) + ' Bytes']
            else:
                lists += ['Modified   : No save']
            return lists
        if bnum == s_buf_num('folders', ''):
            search_term = vim.vars['notmuch_folders'][vc.window.cursor[0] - 1][1].decode()
            if search_term == '':
                return None
            return [search_term]
        msg_id = get_msg_id()
        if msg_id == '':
            return None
        db = notmuch2.Database()
        try:
            msg = db.find(msg_id)
        except LookupError:  # メール・ファイルが全て削除されている場合
            return None
        if f_type != 'notmuch-edit':
            search_term = b_v['search_term'].decode()
        # try:
        #    msg = db.find(msg_id)
        # except LookupError:  # メール・ファイルが全て削除されている場合
        #     return None
        if f_type == 'notmuch-edit':
            lists = []
        elif bnum == s_buf_num('thread', '') \
            or ((search_term in s_buf_num('search', ''))
                and bnum == s_buf_num('search', search_term)):
            lists = ['search term: ' + search_term]
        else:
            lists = []
        lists += ['msg-id     : ' + msg_id, 'tags       : ' + get_msg_tags(msg)]
        for f in msg.filenames():
            if os.path.isfile(f):
                lists += ['file       : ' + str(f),
                          'Modified   : '
                          + datetime.datetime.fromtimestamp(os.path.getmtime(f)).strftime(DATE_FORMAT),
                          'Size       : ' + str(os.path.getsize(f)) + ' Bytes']
            else:
                lists.append('file       : Already Delete.   ' + str(f))
        db.close()
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
    if vim_has('popupwin'):
        vim_popup_atcursor([' ' + x for x in info],  # 左側の罫線に左端の文字が隠される
                           {'border': [1, 1, 1, 1],
                            'borderchars': ['─', '│', '─', '│', '┌', '┐', '┘', '└'],
                            'drag': 1,
                            'close': 'click',
                            'moved': 'any',
                            'filter': "notmuch_py#ClosePopup",
                            'col': 'cursor',
                            'wrap': 0,
                            'mapping': 0})
        # '"minwidth": 400,'+
    else:
        print('\n'.join(info))


def open_original(msg_id, search_term, args):
    """ vim から呼び出しでメール・ファイルを開く """
    def find_mail_file(search_term):  # 条件に一致するファイルを探す
        msgs = dbase.messages(search_term)
        files = []
        for msg in msgs:
            for filename in msg.filenames():
                files.append(filename)
        if not files:
            return ''
        else:
            return str(files[0])

    dbase = notmuch2.Database()
    message = ''
    filename = find_mail_file('(' + search_term + ') id:"' + msg_id + '"')
    filename = str(filename)
    if filename == '':
        message = 'Already Delete/Move/Change folder/tag'
        filename = find_mail_file('id:"' + msg_id + '"')
    dbase.close()
    if filename == '':
        message = 'Not found file.'
    else:
        # 開く前に呼び出し元となるバッファ変数保存
        b = vim.current.buffer
        b_v = b.vars['notmuch']
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
                charset = replace_charset(part.get_content_charset('utf-8'))
                # * 下書きメールを単純にファイル保存した時は UTF-8 にしそれをインポート
                # * BASE64 エンコードで情報がなかった時
                # したときのため、仮の値として指定しておく
                encoding = part.get('Content-Transfer-Encoding')
                if content_type.find('text/') == 0:
                    break
        # for charset in msg_file.get_charsets():
        #     if charset is not None:
        #         break  # 複数の文字コードであっても vim 自体がその様なファイルに対応していないだろうから、最初の文字コードで開く
        if encoding is not None:
            encoding = encoding.lower()
        active_win = b.number
        if encoding == 'quoted-printable' or encoding == 'base64':
            vim.command(vim.vars['notmuch_open_way']['edit'].decode() + ' ' + filename)
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
        f_type = buf_kind()
        if f_type == 'search' or f_type == 'view':
            vim.command('AuEdit(' + str(active_win) + ', "' + search_term + '", 1)')
        else:
            vim.command('AuEdit(' + str(active_win) + ', "", 1)')
        if get_mailbox_type() == 'Maildir':
            draft_dir = PATH + os.sep + '.draft'
        else:
            draft_dir = PATH + os.sep + 'draft'
        if filename.startswith(draft_dir + os.sep) or 'draft' in tags.decode().split(' '):
            vim.command('setlocal filetype=notmuch-draft | call s:AuWriteDraft() | cd '
                        + os.path.dirname(
                            vim_getbufinfo(s_buf_num('folders', ''))[0]['name'].decode()[17:]))
        else:
            vim.command('setlocal filetype=notmuch-edit')
    if message != '':
        vim.command('redraw')  # redraw しないと次のメッセージがすぐに消えてしまう
        print(message)
    return [0, 0]  # ダミー・リストを返す


def send_mail(filename):
    """
    ファイルをメールとして送信←元のファイルは削除
    添付ファイルのエンコードなどの変換済みデータを送信済み保存
    """
    for b in vim.buffers:
        if b.name == str(filename):  # Vim で開いている
            if b.options['modified'] or b.options['bufhidden'] != b'':
                # 更新もしくは隠れバッファ等でもない普通に開いているバッファなので送信しない
                return
    with open(filename, 'r') as fp:
        msg_data = fp.read()
        # msg_file = email.message_from_file(fp) を用いるとヘッダがエンコードされる+不正なヘッダ書式をチェック出来ない
    msg_id = []
    if send_str(msg_data, msg_id):
        os.remove(filename)
        return True
    else:
        print_warring('Sending Error')
        return False


def send_vim_buffer():
    msg_data = '\n'.join(vim.current.buffer[:])
    msg_id = []
    if send_str(msg_data, msg_id):
        if msg_id:  # タグの反映
            marge_tag(msg_id[0], True)
        if len(vim_getbufinfo()) == 1:  # 送信用バッファのみ
            vim.command('cquit')
        f = vim.current.buffer.name
        vim.command('bwipeout!')
        if get_mailbox_type() == 'Maildir':
            f = re.sub('[DFPRST]+$', '', f) + '*'
        rm_file_core(f)
        return True
    return False


def marge_tag(msg_id, send):
    """
    下書きバッファと notmuch database のタグをマージ
    send 送信時か?→draft, unread タグは削除
    """
    global DBASE
    b = vim.current.buffer
    msg = change_tags_before(msg_id)
    if msg is None:
        DBASE.close()
    else:
        b_v = b.vars['notmuch']
        b_tag = b_v['tags'].decode().split(' ')
        b_tag = ['unread' if i == '📩' else i for i in b_tag]
        b_tag = ['draft' if i == '📝' else i for i in b_tag]
        b_tag = ['flagged' if i == '⭐' else i for i in b_tag]
        b_tag = ['Trash' if i == '🗑' else i for i in b_tag]
        b_tag = ['attachment' if i == '📎' else i for i in b_tag]
        b_tag = ['encrypted' if i == '🔑' else i for i in b_tag]
        b_tag = ['signed' if i == '🖋️' else i for i in b_tag]
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
        for t in msg.tags:
            m_tag.append(t)
        for t in m_tag:
            if t in ['attachment', 'encrypted', 'signed']:
                continue
            if not (t in b_tag):
                del_tag.append(t)
        for t in b_tag:
            if not (t in m_tag):
                add_tag.append(t)
        with msg.frozen():
            delete_msg_tags(msg.tags, del_tag)
            add_msg_tags(msg.tags, add_tag)
        change_tags_after(msg, False)


def get_flag(s, search):
    """ s に search があるか? """
    return re.search(search, s, re.IGNORECASE) is not None


def send_str(msg_data, msgid):
    """ 文字列をメールとして保存し設定に従い送信済みに保存 """
    PGP_ENCRYPT = 0x10
    PGP_SIGNATURE = 0x20
    PGPMIME_ENCRYPT = 0x100
    PGPMIME_SIGNATURE = 0x200
    SMIME_ENCRYPT = 0x1000
    SMIME_SIGNATURE = 0x2000
    PGPMIME_SUBJECT = 0x10000
    PGPMIME_PUBLIC = 0x20000
    PGPMIME_SUBJECT_ON = PGPMIME_SUBJECT | PGPMIME_ENCRYPT
    PGPMIME_PUBLIC_ON = PGPMIME_PUBLIC | PGPMIME_ENCRYPT
    ALL_ENCRYPT = SMIME_ENCRYPT | PGP_ENCRYPT | PGPMIME_ENCRYPT
    ALL_SIGNATURE = SMIME_SIGNATURE | PGP_SIGNATURE | PGPMIME_SIGNATURE
    HEADER_ADDRESS = ['Sender', 'Resent-Sender', 'From', 'Resent-From',
                      'To', 'Resent-To', 'Cc', 'Resent-Cc', 'Bcc', 'Resent-Bcc']

    def set_header(msg, header, data):  # エンコードしてヘッダ設定
        for charset in sent_charset:
            try:
                if charset == 'us-ascii' or charset == 'ascii':
                    data.encode(charset)
                    # ↑ASCII 指定で ASCII 以外が含まれると全て UTF-8 として扱うので本当に ASCII 変換可能か試す
                    msg[header] = data
                else:
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
        for charset in sent_charset:
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
        if mimetype is None:
            try:
                import magic
                mimetype = magic.from_file(path, mime=True)
            except ImportError:
                pass
            except ModuleNotFoundError:
                pass
        if mimetype == 'message/rfc822' \
                or mimetype == 'message/rfc2822' \
                or path.find(PATH + os.sep) == 0:
            with open(path, 'rb') as fp:
                part = MIMEBase('message', mimetype[8:])
                msg_f = email.message_from_binary_file(fp)
                part.attach(msg_f)
                part.set_default_type(mimetype)
                encoding = msg_f.get('Content-Transfer-Encoding')
                if encoding is not None:
                    part['Content-Transfer-Encoding'] = encoding
            msg.attach(part)
            return True
        if mimetype is None or mimeencoding is not None:
            print_warring('Not found MIME Type.  Attach with \'application/octet-stream\'')
            mimetype = 'application/octet-stream'
        maintype, subtype = mimetype.split('/')
        if maintype == 'text':
            part = MIMEBase(_maintype='text', _subtype=subtype)
            for charset in sent_charset:
                with open(path, 'rb') as fp:
                    try:
                        bs = fp.read()
                        s = bs.decode(charset)
                        if (charset == 'ascii' or charset == 'us-ascii') and '\x1B' in s:
                            continue
                        part.set_payload(s, charset=charset)
                        charset = '; charset="' + charset + '"'
                        break
                    except UnicodeDecodeError:
                        continue
            else:
                part = attach_binary(path, maintype, subtype, name_param, file_param)
                import chardet
                charset = chardet.detect(bs)['encoding']
                if charset is None:
                    charset = ''
                else:
                    try:
                        charset = '; charset="' + charset.lower() + '"'
                    except (ImportError, ModuleNotFoundError):
                        charset = ''
                        pass
            part.replace_header('Content-Type', 'text/' + subtype + charset
                                + '; name="' + name_param['name'] + '"')
        else:
            part = attach_binary(path, maintype, subtype, name_param, file_param)
        part.add_header('Content-Disposition', 'attachment', **file_param)
        msg.attach(part)
        return True

    def set_header_address(msg, header, address):  # ヘッダにエンコードした上でアドレスをセット
        pair = ''
        for s in address:
            for charset in sent_charset:
                try:
                    d_s = email.utils.formataddr(email.utils.parseaddr(s), charset)
                    break
                except UnicodeEncodeError:
                    pass
            else:
                d_s = email.utils.formataddr(email.utils.parseaddr(s), 'utf-8')
            pair += ', ' + d_s
        msg[header] = pair[2:]

    def get_user():  # get User ID and domain from mail address setting
        if 'notmuch_from' in vim.vars:
            mail_address = vim.vars['notmuch_from'][0]['address'].decode()
        if mail_address is None:
            return get_config('user.primary_email')
        return mail_address

    def encrypt(s, header, charset):
        def adr_only(header):
            adr = []
            for s in ['To', 'From', 'Cc', 'Bcc']:
                if s in header:
                    adr += header[s]
            ls = []
            for i in adr:
                ls.append(email2only_address(i).lower())
            return list(set(ls))

        if flag & SMIME_ENCRYPT:
            cmd = ['gpgsm', '--encrypt', '--base64', '--output', '-']
        else:
            if flag & PGP_SIGNATURE:
                local_user = email2only_address(header['From'][0])
                cmd = ['gpg', '--sign', '--local-user', local_user, '--encrypt', '--armor', '--output', '-']
            else:
                cmd = ['gpg', '--encrypt', '--armor', '--output', '-']
        if shutil.which(cmd[0]) is None:
            print_error('Can not execute ' + cmd[0] + '.')
            return False, s
        for i in adr_only(header):
            cmd.append('--recipient')
            cmd.append(i)
        body_tmp = temp_dir + 'body.tmp'
        # with open(body_tmp, 'w', encoding=charset, newline='\r\n') as fp:
        #     fp.write(s)  # UTF-8 以外が保存できるようにエンコードを指定し、改行コードを CR+LF に統一して保存
        with open(body_tmp, 'w', encoding=charset) as fp:
            fp.write(s)  # UTF-8 以外が保存できるようにエンコードを指定して保存
        cmd.append(body_tmp)
        ret = run(cmd, stdout=PIPE, stderr=PIPE, text=True)
        # ret = run([cmd, '--decrypt'], input=decrypt, stdout=PIPE, stderr=PIPE)
        rm_file_core(body_tmp)
        if ret.returncode:
            print_error(ret.stderr)
            return False, s
        return True, ret.stdout

    def signature(s, header, charset):
        local_user = email2only_address(header['From'][0])
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
            print_warring('Programming Error')
            return False
        if shutil.which(cmd[0]) is None:
            print_error('Can not execute ' + cmd[0] + '.')
            return False, s
        body_tmp = temp_dir + 'body.tmp'
        with open(body_tmp, 'w', encoding=charset,  # UTF-8 以外が保存できるようにエンコードを指定
                  newline='\r\n') as fp:  # 署名用に改行コード CR+LF 指定
            fp.write(s)
        cmd.append(body_tmp)
        ret = run(cmd, stdout=PIPE, stderr=PIPE, text=True)
        if ret.returncode:
            print_warring(ret.stderr)
            return False, s
        rm_file_core(body_tmp)
        return True, ret.stdout

    def get_header_ls():  # ヘッダ文字列情報をリストに変換
        h_data = {}  # key:ヘッダ名、value:ヘッダの中身 (アドレスの時だけリスト)
        pre_h = ''
        attach = []
        flag = 0
        ignore_data = ['date', 'resent-date',  # 必ず付け直すヘッダ
                       'message-id', 'resent-message-id',
                       'content-type', 'content-transfer-encoding']
        for h in headers.split('\n'):
            match = re.match(r'^[A-Za-z-]+:\s*', h)
            if h == '':
                pass
            elif match is None:
                match = RE_TOP_SPACE.match(h)
                if match is None:
                    print_error('Illegal header:' + h)
                    return None, None, None
                h_data[pre_h] += h[match.end():]
            else:
                h_term = h[:h.find(':')]
                h_item = h[match.end():]
                h_term_l = h_term.lower()
                if (h_term_l in ignore_data) or h_item == '':
                    continue
                if h_term_l == 'attach':
                    attach.append(h_item)
                    continue
                elif h_term_l == 'encrypt':
                    flag_check = (get_flag(h_item, r'\bS[/-]?MIME\b') * SMIME_ENCRYPT) \
                        | (get_flag(h_item, r'\bPGP\b') * PGP_ENCRYPT) \
                        | (get_flag(h_item, r'\bPGP[/-]?MIME\b') * PGPMIME_ENCRYPT) \
                        | (get_flag(h_item, r'\bSubject\b') * PGPMIME_SUBJECT) \
                        | (get_flag(h_item, r'\bPublic-?Key\b') * PGPMIME_PUBLIC)
                    if not flag_check:
                        print_error('The encryption method is wrong.')
                        return None, None, None
                    flag |= flag_check
                elif h_term_l == 'signature':
                    flag_check = (get_flag(h_item, r'\bS[/-]?MIME\b') * SMIME_SIGNATURE) \
                        | (get_flag(h_item, r'\bPGP\b') * PGP_SIGNATURE) \
                        | (get_flag(h_item, r'\bPGP[/-]?MIME\b') * PGPMIME_SIGNATURE)
                    if not flag_check:
                        print_error('The signature method is wrong.')
                        return None, None, None
                    flag |= flag_check
                # 宛先はこの後も書き換えが行われるので、ヘッダ名の大文字小文字統一
                elif h_term_l == 'sender':
                    h_term = 'Sender'
                elif h_term_l == 'from':
                    h_term = 'From'
                elif h_term_l == 'to':
                    h_term = 'To'
                elif h_term_l == 'cc':
                    h_term = 'Cc'
                elif h_term_l == 'bcc':
                    h_term = 'Bcc'
                elif h_term_l == 'resent-sender':
                    h_term = 'Resent-Sender'
                elif h_term_l == 'resent-from':
                    h_term = 'Resent-From'
                elif h_term_l == 'resent-to':
                    h_term = 'Resent-To'
                elif h_term_l == 'resent-cc':
                    h_term = 'Resent-Cc'
                elif h_term_l == 'resent-bcc':
                    h_term = 'Resent-Bcc'
                elif h_term_l == 'references':
                    h_term = 'References'
                elif h_term_l == 'subject':
                    h_term = 'Subject'
                if h_term in ['To', 'Cc', 'Bcc',
                              'Resent-To', 'Resent-Cc', 'Resent-Bcc'] \
                        and h_term in h_data:
                    h_data[h_term] += ',' + h_item
                else:
                    h_data[h_term] = h_item
                pre_h = h_term
        # 暗号化・署名が複数指定されていた時、暗号化と署名方法に矛盾していた時のために flag を指定し直す
        if flag & SMIME_ENCRYPT:
            flag = SMIME_ENCRYPT | (SMIME_SIGNATURE if flag & ALL_SIGNATURE else 0x0)
        elif flag & PGPMIME_ENCRYPT:
            flag = PGPMIME_ENCRYPT | (PGPMIME_SIGNATURE if flag & ALL_SIGNATURE else 0x0) \
                | (flag & PGPMIME_SUBJECT) | (flag & PGPMIME_PUBLIC)
        elif flag & PGP_ENCRYPT:
            flag = PGP_ENCRYPT | (PGP_SIGNATURE if flag & ALL_SIGNATURE else 0x0)
        elif flag & SMIME_SIGNATURE:
            flag = SMIME_SIGNATURE
        elif flag & PGPMIME_SIGNATURE:
            flag = PGPMIME_SIGNATURE
        elif flag & PGP_SIGNATURE:
            flag = PGP_SIGNATURE
        for h_term in HEADER_ADDRESS:
            if h_term in h_data:
                h_data[h_term] = uniq_address(address2ls(h_data[h_term]))
        h_data_k = list(h_data.keys())
        if 'From' in h_data_k or 'Resent-From' in h_data_k:
            h_data_changed = {}
        else:
            h_data_changed = {'From': [get_user()]}
        for h in ['From', 'Sender', 'To', 'Cc', 'Bcc', 'Subject']:
            if h in h_data_k:
                h_data_changed[h] = h_data[h]
                del h_data[h]
        if not ('Subject' in h_data_k):
            h_data_changed['Subject'] = ''
        h_data_changed.update(h_data)
        return h_data_changed, attach, flag

    def check_sender(h_data, resent):
        if resent + 'From' in h_data and resent + 'Sender' in h_data:
            if email2only_address(h_data.get(resent + 'From', ['0'])[0]) == \
                    email2only_address(h_data.get(resent + 'Sender', ['1'])[0]):
                del h_data[resent + 'Sender']

    def check_address(data, resent):
        del_duple_adr(header_data, resent + 'Bcc', resent + 'To')
        del_duple_adr(header_data, resent + 'Bcc', resent + 'Cc')
        del_duple_adr(header_data, resent + 'Cc', resent + 'To')
        if resent + 'To' in data:
            return True
        if resent + 'Cc' in data or resent + 'Bcc' in data:
            data[resent + 'To'] = ['undisclosed-recipients: ;']
            return True
        print_warring('No address')
        return False

    def reset_msgid(msg, mail_address, resent):
        mail_address = email2only_address(mail_address)
        index = mail_address.find('@')
        if index == -1:
            return None, None
        msgid_usr = mail_address[:index]
        msgid_domain = mail_address[index + 1:]
        if msgid_usr is None:
            msg_id = email.utils.make_msgid()
        else:
            msg_id = email.utils.make_msgid(msgid_usr.upper(), msgid_domain.upper())
        msg_send[resent + 'Message-ID'] = msg_id
        return msg_id

    def reset_date(msg, resent):
        msg_date = email.utils.formatdate(localtime=True)
        msg[resent + 'Date'] = msg_date
        return msg_date

    def send(msg_send):
        msg_from = msg_send['From']
        if type(send_param_setting) is dict:
            for key, prg in send_param_setting.items():
                if key == '*':
                    default_prg = prg
                elif re.search(key, email2only_address(msg_from)) is not None:
                    send_param = prg
                    break
            else:
                send_param = default_prg
        else:
            send_param = send_param_setting
        try:
            pipe = Popen(send_param, stdin=PIPE, stdout=PIPE, stderr=PIPE, encoding='utf8')
        except Exception as err:
            print_error(err)
            return False
        pipe, err = pipe.communicate(msg_send.as_string())
        if err != '':
            print_error(err)
            return False
        print(pipe)
        in_reply = msg_send.get('In-Reply-To')
        if in_reply is not None:  # 送信メールに In-Reply-To が有れば、送信元ファイルに replied タグ追加
            msg = change_tags_before(in_reply.__str__()[1:-1])
            with msg.frozen():
                msg.tags.add('replied')
            change_tags_after(msg, True)
        return True

    def save_draft(msg_send, msg_data, msg_id, date, flag):  # 送信済みファイル保存
        def get_draft_dir():  # 保存先メール・フォルダ取得
            if fcc_mailbox != '' and os.path.isdir(PATH + os.sep + fcc_mailbox):
                return fcc_mailbox
            return vim.vars.get('notmuch_save_sent_mailbox', 'sent').decode()

        sent_dir = get_draft_dir()
        if sent_dir == '':
            return
        make_dir(temp_dir)
        send_tmp = temp_dir + 'send.tmp'
        with open(send_tmp, 'w') as fp:  # utf-8 だと、Mailbox に取り込めないので一度保存してバイナリで読込し直す
            if flag:
                msg_data = msg_data[1:]
                msg_data += '\nDate: ' + date \
                    + '\nContent-Type: text/plain; charset="utf-8"\nContent-Transfer-Encoding: 8bit'
                msg_data += '\nMessage-ID: ' + msg_id
                for attachment in attachments:
                    msg_data += '\nX-Attach: ' + attachment
                msg_data += '\n\n' + mail_context
                fp.write(msg_data)
            else:
                fp.write(msg_send.as_string())
        if not attachments:
            add_tag = [vim.vars['notmuch_sent_tag'].decode()]
        else:
            add_tag = [vim.vars['notmuch_sent_tag'].decode(), 'attachment']
        dbase = notmuch2.Database()
        msg_id = msg_id[1:-1]
        msg = list(dbase.messages(msg_id))
        if msg:
            add_tag.append(msg.tags)
            add_tag.remove('draft')
            add_tag.remove('unread')
        dbase.close()
        move_mail_main(msg_id, send_tmp, sent_dir, ['draft', 'unread'], add_tag, True)  # 送信済み保存
        msgid.append(msg_id)

    def uniq_address(ls):
        uni = []
        for i in ls:
            i_l = email2only_address(i).lower()
            duple = [j for j, k in enumerate(uni) if email2only_address(k).lower() == i_l]
            if duple == []:
                uni.append(i)
        return uni

    def merge_address(data, a, b):
        if not (b in data):
            return
        if not (a in data):
            data[a] = data[b]
            del data[b]
            return
        diff_ls = []
        for i in data[b]:
            i_l = email2only_address(i).lower()
            duple = [j for j, k in enumerate(data[a]) if email2only_address(k).lower() == i_l]
            if duple == []:
                diff_ls.append(i)
        data[a] += diff_ls
        del data[b]

    def del_duple_adr(data, main, delete):  # data にある main ヘッダにある delete ヘッダのアドレスを削除
        # delete ヘッダが空になれば data[delete] 削除
        if not (main in data) or not (delete in data):
            return
        del_ls = data[delete]
        for i in data[main]:
            duple = [j for j, k in enumerate(del_ls)
                     if email2only_address(k).lower() == email2only_address(i).lower()]
            for i in reversed(duple):
                del del_ls[i]
        if del_ls == []:
            del data[delete]
        else:
            data[delete] = del_ls

    def make_send_message(msg_send, h_data, context, flag):  # そのまま転送以外の送信データの作成
        def set_content(msg, s, charset, encoding):  # 本文と添付ファイルの追加
            def set_attach_main(msg):  # 添付ファイルを付けるかどうかの場合分け
                def set_attach(msg):  # 実際の添付ファイルの追加
                    for attachment in attachments:  # 添付ファイル追加
                        if not attach_file(msg, attachment):
                            return False
                    return True

                def attach_pub_key(msg):
                    ret = run(['gpg', '--armor', '--export',
                               email2only_address(h_data['From'][0])],
                              stdout=PIPE, stderr=PIPE, text=True).stdout
                    if ret != '':
                        part = Message()
                        part['Content-Type'] = 'application/pgp-keys; name="OpenPGP_public_key.asc"'
                        part['Content-Disposition'] = 'attachment; filename="OpenPGP_public_key.asc"'
                        part['Content-Description'] = 'OpenPGP public key'
                        part['Content-Transfer-Encoding'] = '7bit'
                        part.set_payload(ret)
                        msg.attach(part)

                if not attachments \
                        and (flag & PGPMIME_PUBLIC_ON) != PGPMIME_PUBLIC_ON:
                    msg.set_payload(context, charset)
                    msg.replace_header('Content-Transfer-Encoding', encoding)
                    return True
                part = Message()
                part.set_payload(context, charset)
                part.replace_header('Content-Transfer-Encoding', encoding)
                msg['Content-Type'] = 'multipart/mixed'
                msg.attach(part)
                if not set_attach(msg):
                    return False
                if (flag & PGPMIME_PUBLIC_ON) == PGPMIME_PUBLIC_ON:
                    attach_pub_key(msg)
                return True

            if (flag & PGPMIME_SUBJECT_ON) != PGPMIME_SUBJECT_ON:
                if set_attach_main(msg):
                    return True
                return False
            else:  # PGP/MIME でヘッダを暗号化部分に写し Subject だけは元を書き換え
                msg['Content-Type'] = 'multipart/mixed; protected-headers="v1"'
                for h in msg_send.keys():
                    msg[h] = msg_send[h]
                msg_send.replace_header('Subject', '...')
                part = Message()
                if not set_attach_main(part):
                    return False
                msg.attach(part)
                return True

        def set_mime_sig(msg, mail_body):
            ret, sig = signature(mail_body.as_string(), h_data, charset)
            if not ret:
                return False
            msg_sig = Message()
            if flag & SMIME_SIGNATURE:
                msg_sig['Content-Type'] = 'application/pkcs7-signature; name="smime.p7s"'
                msg_sig['Content-Transfer-Encoding'] = 'base64'
                msg_sig['Content-Disposition: attachment'] = 'filename="smime.p7s"'
                msg_sig['Content-Description'] = 'S/MIME Cryptographic Signature'
            else:
                msg_sig['Content-Type'] = 'application/pgp-signature; name="signature.asc"'
                msg_sig['Content-Description'] = 'OpenPGP digital signature'
            msg_sig.set_payload(sig)
            msg.attach(mail_body)
            msg.attach(msg_sig)
            return True

        if ('utf-8' in sent_charset):  # utf-8+8bit を可能にする 無いとutf-8+base64
            email.charset.add_charset(
                'utf-8', email.charset.SHORTEST, None, 'utf-8')
        for charset in sent_charset:  # 可能な charset の判定とエンコード方法の選択
            try:
                context.encode(charset)
                if charset == 'utf-8':
                    t_encoding = '8bit'
                else:
                    t_encoding = '7bit'
                break
            except UnicodeEncodeError:
                pass
        else:
            charset = 'utf-8'
            t_encoding = 'base64'
        if not (flag & (ALL_SIGNATURE | ALL_ENCRYPT)):
            if set_content(msg_send, context, charset, t_encoding):
                return True
        elif flag & PGP_ENCRYPT:
            ret, mail_body = encrypt(context, h_data, charset)
            if not ret:
                return False
            if set_content(msg_send, mail_body, charset, t_encoding):
                return True
        elif flag & PGP_SIGNATURE:
            # PGP 署名では ASCII 以外 quoted-printable
            if charset != 'us-ascii' and charset != 'ascii':
                t_encoding = 'quoted-printable'
            msg = Message()
            msg.set_payload(context, charset)
            context = msg.get_payload()
            ret, mail_body = signature(context, h_data, charset)
            if not ret:
                return False
            if set_content(msg_send, mail_body, charset, t_encoding):
                return True
        else:  # PGP/MIME, S/MIME
            if (flag & ALL_SIGNATURE) and not (flag & ALL_ENCRYPT):
                # 暗号化なしの署名付きは quoted-printable か base64 使用
                if charset == 'utf-8':
                    t_encoding = 'base64'
                else:
                    t_encoding = 'quoted-printable'
            mail_body = Message()
            if not set_content(mail_body, context, charset, t_encoding):
                return False
        if flag & (SMIME_SIGNATURE | PGPMIME_SIGNATURE):  # S/MIME, PGP/MIME 電子署名
            if flag & SMIME_SIGNATURE:
                micalg_kind = 'sha-256'
                sig_kind = 'pkcs7'
            else:
                micalg_kind = 'pgp-sha1'
                sig_kind = 'pgp'
            if flag & (SMIME_ENCRYPT | PGPMIME_ENCRYPT):  # この後 S/MIME, PGP/MIME 暗号化する
                mail_sig = mail_body
                mail_body = MIMEBase(_maintype='multipart', _subtype='signed', micalg=micalg_kind,
                                     protocol='application/' + sig_kind + '-signature')
                if not (set_mime_sig(mail_body, mail_sig)):
                    return False
            else:
                msg_send['Content-Type'] = 'multipart/signed; micalg="' + micalg_kind + '"; ' \
                    + 'protocol="application/' + sig_kind + '-signature"'
                if set_mime_sig(msg_send, mail_body):
                    return True
        if (flag & SMIME_ENCRYPT):  # S/MIME 暗号化
            if SMIME_SIGNATURE:  # 改行コードを CR+LF に統一して渡す
                ret, mail_body = encrypt(re.sub(r'(\r\n|\n\r|\n|\r)', r'\r\n',
                                                mail_body.as_string()), h_data, charset)
            else:
                ret, mail_body = encrypt(mail_body.as_string(), h_data, charset)
            if not ret:
                return False
            msg_send['Content-Type'] = 'application/pkcs7-mime; name="smime.p7m"; smime-type="enveloped-data"'
            msg_send['Content-Transfer-Encoding'] = 'base64'
            msg_send['Content-Disposition'] = 'attachment; filename="smime.p7m"'
            msg_send['Content-Description'] = 'S/MIME Encrypted Message'
            msg_send.set_payload(mail_body)
            return True
        elif (flag & PGPMIME_ENCRYPT):  # PGP/MIME 暗号化
            msg0 = Message()
            msg0['Content-Type'] = 'application/pgp-encrypted'
            msg0['Content-Description'] = 'PGP/MIME version identification'
            msg0.set_payload('Version: 1\n')
            ret, mail_body = encrypt(mail_body.as_string(), h_data, charset)
            if not ret:
                return False
            msg = Message()
            msg['Content-Type'] = 'application/octet-stream; name="encrypted.asc"'
            msg['Content-Description'] = 'OpenPGP encrypted message'
            msg['Content-Disposition'] = 'inline; filename="encrypted.asc"'
            msg.set_payload(mail_body)
            msg_send['Content-Type'] = 'multipart/encrypted; protocol="application/pgp-encrypted"'
            msg_send.attach(msg0)
            msg_send.attach(msg)
            return True
        return False

    if 'notmuch_send_encode' in vim.vars:  # 送信文字コード
        sent_charset = [str.lower() for str in vim.eval('g:notmuch_send_encode')]
    else:
        sent_charset = ['us-ascii', 'iso-2022-jp', 'utf-8']
    if 'notmuch_send_param' in vim.vars:   # 送信プログラムやそのパラメータ
        send_param_setting = vim.eval('g:notmuch_send_param')
    else:
        send_param_setting = ['sendmail', '-t', '-oi']
    if type(send_param_setting) is dict:
        for prg in send_param_setting.values():
            if shutil.which(prg[0]) is None:
                print_error('\'' + prg[0] + '\' is not executable.')
                return False
    else:
        if shutil.which(send_param_setting[0]) is None:
            print_error('\'' + send_param_setting[0] + '\' is not executable.')
            return False
    temp_dir = get_temp_dir()
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
    if header_data is None:
        return False
    fcc_mailbox = ''
    if 'Resent-From' in header_data:  # そのまま転送
        if len(attachments) != 1:
            print_error('The transfer source file is not specified (attached).')
            return False
        f = attachments[0]
        if f.find(PATH) != 0:
            if not ('References' in header_data):
                print_error('There is no transfer source file.: ' + f)
                return False
            dbase = notmuch2.Database()
            msg = dbase.find(header_data['References'][1:-1])
            if msg is None:
                dbase.close()
                print_error('There is no transfer source file.: ' + f)
                return False
            for f in msg.filenames():
                if os.path.isfile(f):
                    attachments[0] = str(f)
                    break
            dbase.close()
        try:
            with open(f, 'r') as fp:
                msg_send = email.message_from_file(fp)
        except UnicodeDecodeError:
            print_error('The transfer source file is not email message.: ' + f)
            return False
        for i in ['Sender', 'From', 'To', 'Cc', 'Bcc']:
            merge_address(header_data, 'Resent-' + i, i)
        check_sender(header_data, 'Resent-')
        if not check_address(header_data, 'Resent-'):
            return False
        # ヘッダ設定
        msg_data = '\nFrom: ' + header_data['Resent-From'][0] \
            + '\nTo: ' + ', '.join(header_data['Resent-To'])
        for h in ['Resent-Sender', 'Resent-From', 'Resent-To', 'Resent-Cc', 'Resent-Bcc']:
            if h in header_data:
                h_data = header_data[h]
                msg_data += '\n' + h + ': ' + ', '.join(h_data)
                set_header_address(msg_send, h, h_data)
        for h in ['Subject', 'References']:
            if h in header_data:
                h_data = header_data[h]
                msg_data += '\n' + h + ': ' + h_data
        msg_date = reset_date(msg_send, 'Resent-')
        msg_data += '\nResent-Date: ' + msg_date
        msg_id = reset_msgid(msg_send, header_data['Resent-From'][0], 'Resent-')
        msg_data += '\nResent-Message-ID: ' + msg_id
        if not send(msg_send):
            return False
        save_draft(msg_send, msg_data, msg_id, msg_date, True)
    else:
        check_sender(header_data, '')
        if not check_address(header_data, ''):
            return False
        msg_data = ''  # 送信済みとして下書きを使う場合に備えたデータ初期化
        msg_send = Message()
        # ヘッダ設定
        for header_term, h_data in header_data.items():
            header_lower = header_term.lower()
            if header_lower == 'fcc':
                fcc_mailbox = h_data
                continue
            elif header_lower == 'encrypt' or header_lower == 'signature':
                continue
            elif header_term in HEADER_ADDRESS:
                msg_data += '\n' + header_term + ': ' + ', '.join(h_data)
                set_header_address(msg_send, header_term, h_data)
            else:
                msg_data += '\n' + header_term + ': ' + h_data
                set_header(msg_send, header_term, h_data)
        msg_date = reset_date(msg_send, '')
        msg_id = reset_msgid(msg_send, header_data['From'][0], '')
        if not make_send_message(msg_send, header_data, mail_context, flag):
            return False
        if not send(msg_send):
            return False
        save_draft(msg_send, msg_data, msg_id, msg_date,
                   vim.vars.get('notmuch_save_draft', 0))
    return True


def send_search(search_term):
    dbase = notmuch2.Database()
    for msg in dbase.messages(search_term):
        files = msg.filenames()
        for f in files:
            if os.path.isfile(f):
                if send_mail(f):
                    for i in files:  # 同じ内容のファイルが複数あった時、残りを全て削除
                        if os.path.isfile(i):
                            os.remove(i)
                break
        else:
            print_warring('Not exist mail file.')
    dbase.close()
    return


def send_vim():
    b = vim.current.buffer
    bufnr = b.number
    b_v = b.vars['notmuch']
    if b.options['filetype'] == b'notmuch-draft':
        if not send_vim_buffer():
            return
    else:
        sent_tag = ' ((folder:draft or folder:.draft or tag:draft) not tag:' \
            + vim.vars['notmuch_sent_tag'].decode() + ' not tag:Trash not tag:Spam)'
        buf_num = s_buf_num_dic()
        if bufnr == buf_num['folders']:
            send_search(sent_tag)
        elif 'search_term' in b_v:
            s = b_v['search_term'].decode()
            if bufnr == buf_num['thread'] \
                    or (s in buf_num['search'] and bufnr == buf_num['search'][s]):
                send_search(s + sent_tag)
            else:  # buf_num['show'] または buf_num['view'][s]
                msg_id = get_msg_id()
                if msg_id == '':
                    return
                send_search('id:' + msg_id + sent_tag)
    if 'folders' in s_buf_num_dic():
        reprint_folder2()


def new_mail(s):
    """ 新規メールの作成 s: mailto プロトコルを想定 """
    def get_mailto(s, headers):  # mailto プロトコルからパラメータ取得
        if not s:
            headers['to'] = ''
            return
        s = s[0]
        if s[:7] == 'mailto:':
            s = unquote(s)
            s = s[7:]
        re_match = re.search(r'\?[A-Za-z-]+=', s)
        if re_match is None:
            headers['to'] = s
            return
        headers['to'] = s[:re_match.start()]
        s = s[re_match.start():]
        while True:
            header_len = re_match.end() - re_match.start()
            header = s[1:header_len - 1].lower()
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
            win_nr = vim_bufwinnr("folders")
            for w in vim.windows:
                if w.number == win_nr:
                    s = vim.vars['notmuch_folders'][w.cursor[0] - 1][1].decode()
                    break
            to = ''
            for i in vim.vars.get('notmuch_to', []):
                d = i[0].decode()
                if d == '*':
                    to = i[1].decode()
                elif re.search(r'\b' + re.escape(d) + r'\b', s) is not None:
                    return i[1].decode()
            return to

        msg_id = get_msg_id()
        to = ''
        if msg_id != '':
            dbase = notmuch2.Database()
            for i in vim.vars.get('notmuch_to', []):
                s = i[0].decode()
                if dbase.count_messages('(' + s + ') and id:"' + msg_id + '"'):
                    return i[1].decode()
            dbase.close()
        elif is_same_tabpage('folders', ''):
            to = get_user_To_folder()
        return to

    headers = {'subject': ''}
    get_mailto(s, headers)
    b = vim.current.buffer
    if headers['to'] == '':
        headers['to'] = get_user_To(b)
    active_win = b.number
    before_make_draft(active_win)
    b = vim.current.buffer
    b.vars['notmuch'] = {}
    b.vars['notmuch']['subject'] = headers['subject']
    add_head = 0x01
    for header in vim.vars['notmuch_draft_header']:
        header = header.decode()
        header_l = header.lower()
        if header_l in headers:
            h_item = re.split(r'[\n\r]', headers.pop(header_l))
            b.append(header + ': ' + h_item[0])
            if len(h_item) > 1:
                for i in h_item[1:]:
                    b.append('\t' + i)
        elif header_l == 'attach':  # これだけは必ず最後
            add_head = 0x03
        else:
            b.append(header + ': ')
    for header in headers:
        b.append(header + ': ' + headers[header])
    after_make_draft(b, None, add_head)
    vim.command('AuNewMail()')


def address2ls(adr):
    """ To, Cc ヘッダのアドレス群をリストに """
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


def reply_mail():
    """ 返信メールの作成 """
    def delete_duplicate_addr(x_ls, y_ls):
        """
        x_ls から y_ls と重複するアドレス削除
        重複が合ったか? 最初に見つかった重複アドレスを返す
        y_ls は実名の削除されたアドレスだけが前提
        """
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

    def uniq_adr(ls, adr):
        only_adr = []
        for i in ls:
            only_adr.append(email2only_address(i))
        if email2only_address(adr) in only_adr:
            return ls
        else:
            return ls + [adr]

    def to2from(str):  # g:notmuch_from に一致する From を返す
        str = email2only_address(str)
        adr = ''
        for j in vim.vars.get('notmuch_from', []):
            l_to = j.get('To', b'').decode()
            if l_to == '' or l_to == '*':
                continue
            elif l_to == '*':
                adr = j['address'].decode()
            elif re.search(l_to, str) is not None:
                return j['address'].decode()
        return adr

    def to2fromls(ls):  # リスト ls から g:notmuch_from に一致する From を返す
        for i in ls:
            adr = to2from(i)
            if adr != '':
                return adr
        return ''

    global DBASE
    active_win, msg_id, subject = check_org_mail()
    if not active_win:
        return
    msg_data = get_mail_body(active_win)
    before_make_draft(active_win)
    b = vim.current.buffer
    b.vars['notmuch'] = {}
    b_v = b.vars['notmuch']
    b_v['org_mail_body'] = msg_data
    DBASE = notmuch2.Database()
    msg = DBASE.find(msg_id)
    msg_f = open_email_file_from_msg(msg)
    if msg_f is None:
        DBASE.close()
        print_error('Reply source email has been deleted.')
        return
    headers = vim.vars['notmuch_draft_header']
    recive_from_name = msg.header('From')
    b_v['org_mail_from'] = email2only_name(recive_from_name)
    recive_to_name = get_msg_header(msg_f, 'To')
    from_ls = [email2only_address(get_config('user.primary_email'))]
    for i in vim.vars.get('notmuch_from', []):
        from_ls.append(email2only_address(i['address'].decode()))
    send_from_name = ''
    cc_name = address2ls(get_msg_header(msg_f, 'Cc'))
    if email2only_address(recive_from_name) in from_ls:  # 自分のメールに対する返信
        send_to_name = recive_to_name
        send_from_name = recive_from_name
        recive_to_name = [recive_to_name]
    else:
        recive_to_name = address2ls(recive_to_name)
        addr_exist = False
        addr_exist, send_from_name = delete_duplicate_addr(recive_to_name, from_ls)
        addr_tmp, send_tmp = delete_duplicate_addr(cc_name, from_ls)
        if not addr_exist:
            addr_exist = addr_tmp
            send_from_name = send_tmp
        send_to_name = ', '.join(uniq_adr(recive_to_name, recive_from_name))
    # g:notmuch_from に従って From に書き込む情報置き換え
    send_from_tmp = to2fromls(cc_name + recive_to_name)
    if send_from_tmp == '':
        send_from_tmp = to2from(recive_from_name)
    if send_from_tmp != '':
        send_from_name = send_from_tmp
    add_head = 0x01
    for header in headers:
        header = header.decode()
        header_lower = header.lower()
        if header_lower == 'from':
            b.append('From: ' + send_from_name)
        elif header_lower == 'subject':
            subject = re.sub(r'(re([*^][0-9]+)?: *)+', 'Re: ',
                             'Re: ' + subject, flags=re.IGNORECASE)
            b.append('Subject: ' + subject)
            b_v['subject'] = subject
        elif header_lower == 'to':
            to = get_msg_header(msg_f, 'Reply-To')
            if to == '':
                to = send_to_name
            b.append('To: ' + to)
        elif header_lower == 'cc':
            b.append('Cc: ' + ', '.join(cc_name))
        elif header_lower == 'attach':  # これだけは必ず最後
            add_head = 0x03
        else:
            b.append(header + ': ')
    b_v['org_mail_date'] = email.utils.parsedate_to_datetime(
        msg.header('Date')).strftime('%Y-%m-%d %H:%M %z')
    # date = email.utils.parsedate_to_datetime(msg.header('Date')).strftime(DATE_FORMAT)
    # ↑同じローカル時間同士でやり取りするとは限らない
    after_make_draft(b, msg, add_head | 0x0E)
    vim.command('AuReplyMail()')


def forward_mail():
    windo, msg_id, subject = check_org_mail()
    if not windo:
        return
    msg_data = get_mail_body(windo)  # 実際には後からヘッダ情報なども追加
    DBASE = notmuch2.Database()
    try:
        msg = DBASE.find(msg_id)
    except LookupError:
        DBASE.close()
        print_error('Forward source email has been deleted.')
        return
    msg_data = '\n' + msg_data
    before_make_draft(windo)
    b = vim.current.buffer
    b.vars['notmuch'] = {}
    b_v = b.vars['notmuch']
    cut_line = 70
    msg_f = open_email_file_from_msg(msg)
    if msg_f is None:
        DBASE.close()
        print_error('Forward source email has been deleted.')
        return
    for h in ['Cc', 'To', 'Date', 'Subject', 'From']:
        s = get_msg_header(msg_f, h).replace('\t', ' ')
        if h == 'Subject':
            msg_data = h + ': ' + subject + '\n' + msg_data
            subject = 'FWD:' + subject
            b_v['subject'] = subject
        elif s != '':
            msg_data = h + ': ' + ' ' * (7 - len(h)) + s + '\n' + msg_data
        s_len = 9 + vim_strdisplaywidth(s)
        cut_line = max(cut_line, s_len)
    headers = vim.vars['notmuch_draft_header']
    add_head = 0x01
    for h in headers:
        h = h.decode()
        h_lower = h.lower()
        if h_lower == 'subject':
            b.append('Subject: ' + subject)
        elif h_lower == 'attach':  # これだけは必ず最後
            add_head = 0x03
        else:
            b.append(h + ': ')
    # 本文との境界線作成
    message = 'Forwarded message'
    mark = '-' * int((cut_line - vim_strdisplaywidth(message) - 2) / 2)
    msg_data = mark + ' ' + message + ' ' + mark + '\n' + msg_data
    # 本文との境界線作成終了
    b_v['org_mail_body'] = msg_data
    after_make_draft(b, msg, add_head | 0x04)
    vim.command('AuForwardMail()')


def forward_mail_attach():
    global DBASE
    windo, msg_id, s = check_org_mail()
    if not windo:
        return
    DBASE = notmuch2.Database()
    try:
        msg = DBASE.find(msg_id)
    except LookupError:
        DBASE.close()
        print_error('Forward source email has been deleted.')
        return
    before_make_draft(windo)
    b = vim.current.buffer
    b.vars['notmuch'] = {}
    b_v = b.vars['notmuch']
    add_head = 0x01
    for h in vim.vars['notmuch_draft_header']:
        h = h.decode()
        h_lower = h.lower()
        if h_lower == 'subject':
            s = 'FWD:' + s
            b_v['subject'] = s
            b.append('Subject: ' + s)
        elif h_lower == 'attach':  # 元メールを添付するので何もしない
            add_head = 0x03
        else:
            b.append(h + ': ')
    after_make_draft(b, msg, add_head | 0x1C)
    vim.command('AuNewMail()')


def forward_mail_resent():
    global DBASE
    windo, msg_id, s = check_org_mail()
    if not windo:
        return
    DBASE = notmuch2.Database()
    try:
        msg = DBASE.find(msg_id)
    except LookupError:
        DBASE.close()
        print_error('Forward source email has been deleted.')
        return
    before_make_draft(windo)
    b = vim.current.buffer
    b.vars['notmuch'] = {}
    b_v = b.vars['notmuch']
    s = 'Resent-FWD:' + s
    b_v['subject'] = s
    b.append('Resent-From: ')
    b.append('Resent-To: ')
    b.append('Resent-Cc: ')
    b.append('Resent-Bcc: ')
    b.append('Subject: ' + s)
    b.append('Resent-Sender: ')
    after_make_draft(b, msg, 0x1D)
    b.append('This is resent mail template.')
    b.append('Other Resent-xxx headers and body contents are ignored.')
    b.append('If delete Resent-From, became a normal mail.')
    b.options['modified'] = 0
    vim.command('AuResentMail()')


def before_make_draft(active_win):
    """ 下書き作成の前処理 """
    def get_search_term():  # バッファの種類を調べ、search, view なら search_term を返す
        f_type = buf_kind()
        if f_type == 'search' or f_type == 'view':
            return b.vars['notmuch']['search_term'].decode()
        else:
            return ''

    b = vim.current.buffer
    search_term = get_search_term()
    mailbox_type = get_mailbox_type()
    if b.options['filetype'].decode()[:8] == 'notmuch-' \
            or vim.bindeval('wordcount()["bytes"]') != 0:
        vim.command(vim.vars['notmuch_open_way']['draft'].decode())
    if mailbox_type == 'Maildir':
        mbox_type = mailbox.Maildir
        draft_dir = PATH + os.sep + '.draft'
        for sub in (["tmp", "cur", "new"]):
            if not os.path.isdir(draft_dir + os.sep + sub):
                os.makedirs(draft_dir + os.sep + sub, 0o700)
    else:
        mbox_type = mailbox.MH
        draft_dir = PATH + os.sep + 'draft'
    mbox = mbox_type(PATH)
    if not ('draft' in mbox.list_folders()):
        mbox.add_folder('draft')
    mbox = mbox_type(draft_dir)
    f = str(mbox.add(email.message.Message()))
    mbox.remove(f)
    if mailbox_type == 'Maildir':
        f = draft_dir + os.sep + 'cur' + os.sep + f + ':2,DS'
    else:
        f = draft_dir + os.sep + f
    vim.current.buffer.name = f
    vim.command('setlocal filetype=notmuch-draft')
    vim.command('AuEdit(' + str(active_win) + ', \'' + vim_escape(search_term) + '\', 0)')


def after_make_draft(b, msg, add_head):
    global DBASE
    now = email.utils.localtime()
    msg_id = email.utils.make_msgid()
    b_v = vim.current.buffer.vars
    b_v = b_v['notmuch']
    b_v['date'] = now.strftime(vim.vars.get('notmuch_date_format', b'%Y-%m-%d %H:%M').decode())
    b_v['msg_id'] = msg_id[1:-1]
    b_v['tags'] = 'draft'
    b.append('Date: ' + email.utils.format_datetime(now))
    # Message-ID はなくとも Notmuch は SHA1 を用いたファイルのチェックサムを使って管理できるが tag 追加などをするためには、チェックサムではファイル編集で変わるので不都合
    b.append('Message-ID: ' + msg_id)
    if add_head & 0x1C:
        set_reference(b, msg, add_head & 0x0C)
        if add_head & 0x10:
            for f in msg.filenames():
                if os.path.isfile(f):
                    b.append('Attach: ' + str(f))
                    break
    if msg is not None:
        DBASE.close()
    if add_head & 0x02:
        b.append('Attach: ')
    if add_head & 0x01:
        b.append('')
    vim_op = vim.options
    undolevels = vim_op['undolevels']
    vim_op['undolevels'] = -1
    del b[0]
    vim_op['undolevels'] = undolevels
    b.options['modified'] = 0
    if 'folders' in s_buf_num_dic():
        vim.command('silent cd ' + os.path.dirname(
            vim_getbufinfo(s_buf_num('folders', ''))[0]['name'].decode()[17:]))
    vim.command('AuWriteDraft()')


def save_draft():
    """
    下書きバッファと Notmuch database のタグをマージと notmuch-folders の更新
    下書き保存時に呼び出される
    """
    global DBASE
    # notmuch_new(False)
    # ↑だと上書きで自分を含め呼び出し元の編集バッファを閉じてしまうので、やるとしたら警告を無視して↓
    # run(['notmuch', 'new'], stdout=PIPE, stderr=PIPE)
    b = vim.current.buffer
    msg_id = b.vars['notmuch']['msg_id'].decode()
    b_f = b.name
    db = notmuch2.Database(mode=notmuch2.Database.MODE.READ_WRITE)
    if db.count_messages('id:' + msg_id) == 0:
        db.close()
        vim.command('write ' + b_f)
        run(['notmuch', 'new'], stdout=PIPE, stderr=PIPE)
    else:
        db.close()
    marge_tag(msg_id, False)
    # Maildir だとフラグの変更でファイル名が変わり得るので、その時はバッファのファイル名を変える
    DBASE = notmuch2.Database()
    try:
        msg = DBASE.find(msg_id)
    except LookupError:
        m_f = None
    else:
        m_f = str(next(msg.filenames()))
    if m_f is not None and m_f != b_f:
        vim.command('saveas! ' + m_f)
        Bwipeout(b_f)
        if os.path.isfile(b_f):
            os.remove(b_f)
    reprint_folder()
    DBASE.close()


def Bwipeout(b_n):  # notmuch-thread, notmuch-show でバッファ名変更前の名前で隠しバッファが残っているれば完全に削除する
    b_num = [s_buf_num('folders', '')]
    if 'thread' in s_buf_num_dic():
        b_num.append(s_buf_num('thread', ''))
    if 'show' in s_buf_num_dic():
        b_num.append(s_buf_num('show', ''))
    for v in s_buf_num_dic()['search'].values():
        b_num.append(v)
    for v in s_buf_num_dic()['view'].values():
        b_num.append(v)
    for b in vim.buffers:
        if b.name == b_n:
            if b.number in b_num:
                return
            vim.command('bwipeout! ' + str(b.number))


def delete_autocmd_cursor_mv():  # Vim バッファローカルの CursorMoved/CursorMovedI の autocmd を削除
    vim.command('autocmd! NotmuchPython CursorMoved,CursorMovedI <buffer='
                + str(vim.current.buffer.number) + '>')


def set_new_after():
    """ 新規メールの From ヘッダの設定や署名の挿入 """
    if vim.current.window.cursor[0] < len(vim.current.buffer):
        return
    to, h_from = set_from()
    insert_signature(to, h_from)
    delete_autocmd_cursor_mv()


def check_org_mail():
    """ 返信・転送可能か? 今の bufnr() と msg_id を返す """
    b = vim.current.buffer
    active_win = b.number
    b_v = b.vars['notmuch']
    # JIS 外漢字が含まれ notmcuh データベースの取得結果とは異なる可能性がある
    show_win = s_buf_num('show', '')
    is_search = not (s_buf_num('folders', '') == active_win
                     or s_buf_num('thread', '') == active_win
                     or show_win == active_win)
    if is_search:
        show_win = s_buf_num('view', b_v['search_term'].decode())
    if vim_goto_bufwinid(show_win) == 0:
        return 0, '', ''
    msg_id = get_msg_id()
    if msg_id == '':
        vim_goto_bufwinid(active_win)
        return 0, '', ''
    b_v = vim.current.buffer.vars['notmuch']
    subject = b_v['subject'].decode()
    return active_win, msg_id, subject


def get_mail_body(active_win):
    msg_data = '\n'.join(vim.current.buffer[:])
    match = re.search(r'\n\n', msg_data)
    if match is None:
        vim_goto_bufwinid(active_win)
        return ''
    msg_data = re.sub(r'\n+$', '', msg_data[match.end():])
    match = re.search(r'\n\fHTML part\n', msg_data)
    if match is not None:  # HTML メール・パート削除
        msg_data = msg_data[:match.start()]
    vim_goto_bufwinid(active_win)
    return re.sub(r'^\n+', '', msg_data)


def set_reference(b, msg, flag):
    """
    References, In-Reply-To, Fcc 追加
    In-Reply-To は flag == True
    """
    re_msg_id = ' <' + msg.header('Message-ID') + '>'
    msg_f = open_email_file_from_msg(msg)
    if msg_f is None:
        print_error('Forward source email has been deleted.')
        return
    b.append('References: ' + get_msg_header(msg_f, 'References') + re_msg_id)
    if flag:
        b.append('In-Reply-To:' + re_msg_id)
    fcc = str(next(msg.filenames()))
    fcc = fcc[len(PATH) + 1:]
    if get_mailbox_type() == 'Maildir':
        fcc = re.sub(r'/(new|tmp|cur)/[^/]+', '', fcc)
    else:
        fcc = re.sub('/[^/]+$', '', fcc)
    b.append('Fcc: ' + fcc)


def set_reply_after():
    """ 返信メールの From ヘッダの設定や引用本文・署名の挿入 """
    if vim.current.window.cursor[0] < len(vim.current.buffer):
        return
    to, h_from = set_from()
    b = vim.current.buffer
    b_v = b.vars['notmuch']
    lines = ['On ' + b_v['org_mail_date'].decode() + ', '
             + email2only_name(b_v['org_mail_from'].decode()) + ' wrote:']
    for line in b_v['org_mail_body'].decode().split('\n'):
        lines.append('> ' + line)
    if vim.vars.get('notmuch_signature_prev_quote', 0):
        insert_signature(to, h_from)
        b.append(lines)
    else:
        b.append(lines)
        insert_signature(to, h_from)
    del b_v['org_mail_date']
    del b_v['org_mail_body']
    del b_v['org_mail_from']
    delete_autocmd_cursor_mv()


def set_forward_after():
    """ 返信メールの From ヘッダの設定や引用本文・署名の挿入 """
    if vim.current.window.cursor[0] < len(vim.current.buffer):
        return
    to, h_from = set_from()
    b = vim.current.buffer
    b_v = b.vars['notmuch']
    lines = []
    for line in b_v['org_mail_body'].decode().split('\n'):
        lines.append(line)
    if vim.vars.get('notmuch_signature_prev_forward', 0):
        insert_signature(to, h_from)
        b.append(lines)
    else:
        b.append(lines)
        insert_signature(to, h_from)
    del b_v['org_mail_body']
    delete_autocmd_cursor_mv()


def set_resent_after():
    """ そのまま転送メールの From ヘッダの設定や署名の挿入 """
    if vim.current.window.cursor[0] < len(vim.current.buffer) - 1:
        return
    to, h_from = set_from()
    if to:
        if is_gtk():
            s = vim_confirm('Mail: Send or Write and exit?', '&Send\n&Write\nCancel(&C)', 1, 'Question')
        else:
            s = vim_confirm('Mail: Send or Write and exit?', '&Send\n&Write\n&Cancel', 1, 'Question')
        if s == 1:
            send_vim_buffer()
        elif s == 2:
            vim.command('redraw! | silent exit')
            reprint_folder2()
            # vim.command('echo "\n" | redraw!')
    delete_autocmd_cursor_mv()


def set_from():
    """ 宛先に沿って From ヘッダを設定と b:subject の書き換え """
    def get_user_From(to):  # get From setting
        default_addr = get_config('user.primary_email')
        mail_address = vim.vars.get('notmuch_from', [])
        if len(mail_address) == 0:
            return default_addr
        elif len(mail_address) == 1:
            return mail_address[0]['address'].decode()
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
            lst += str(i + 1) + '. ' \
                + j['id'].decode() + ': ' \
                + j['address'].decode() + '\n'
        while True:
            s = vim_input('Select using From:.  When only [Enter], use default ('
                          + default_addr + ').\n' + lst)
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
        return mail_address[s - 1]['address'].decode()

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
            match = re.match(r'((From|To|Cc|Bcc|Resent-From|Resent-To|Resent-Cc|Resent-Bcc):|\s)\s*(.+)',
                             b_i, flags=re.IGNORECASE)
            if match is None:
                continue
            elif match.group(2) is None and is_addr:
                b[i] = match.group(1) + ' ' + compress_addr_core(match.group(3))
            elif match.group(2) is not None:
                is_addr = True
                b[i] = match.group(1) + ' ' + compress_addr_core(match.group(3))
            elif b_i == '':
                break

    to = []
    h_from = {'from': (0, ''), 'resent-from': (1, '')}
    b = vim.current.buffer
    resent_flag = False
    for i, l in enumerate(b):
        match = re.match(r'(From|To|Cc|Bcc|Resent-From|Resent-To|Resent-Cc|Resent-Bcc|Subject): *(.*)',
                         l, flags=re.IGNORECASE)
        if match is None:
            continue
        h = match.group(1).lower()
        if h == 'subject':
            b.vars['notmuch']['subject'] = match.group(2)
        elif h == 'from':
            h_from['from'] = (i, match.group(2))
        elif h == 'resent-from':
            h_from['resent-from'] = (i, match.group(2))
            resent_flag = True
        else:
            if h.find('resent-') == 0:
                resent_flag = True
            g = match.group(2)
            if g != '':
                to.append(g)
    if h_from['from'][1] == '' and h_from['resent-from'][1] == '':
        h_From = get_user_From(to)
    elif h_from['from'][1] == '':
        h_From = h_from['resent-from'][1]
    else:
        h_From = h_from['from'][1]
    if h_from['resent-from'][0]:  # Resent-From ヘッダがない
        if re.match(r'From:', b[h_from['from'][0]], flags=re.IGNORECASE) is None:
            b.append('From: ' + h_From, h_from['from'][0])
        else:
            b[h_from['from'][0]] = 'From: ' + h_From
    else:
        if h_from['resent-from'][1] == '':
            if re.match(r'Resent-From:', b[h_from['resent-from'][0]], flags=re.IGNORECASE) is not None:
                b[h_from['resent-from'][0]] = 'Resent-From: ' + h_From
            elif resent_flag:  # Resent-From がないだけでなく、Reset-??? 送信先があるときだけ追加
                b.append('Resent-From: ' + h_From, h_from['resent-from'][0])
    to = sorted(set(to), key=to.index)
    compress_addr()
    return to, h_From


def insert_signature(to_name, from_name):
    """ 署名挿入 """
    def get_signature(from_to):  # get signature filename
        if from_to == '':
            return ''
        if 'notmuch_signature' in vim.vars:
            sigs = vim.vars['notmuch_signature']
            from_to = email2only_address(from_to)
            if from_to == '':
                return ''
            if os.name == 'nt':
                sig = sigs.get(from_to, sigs.get('*', b'$USERPROFILE\\.signature'))
            else:
                sig = sigs.get(from_to, sigs.get('*', b'$HOME/.signature'))
            sig = os.path.expandvars(os.path.expanduser(sig.decode()))
        elif os.name == 'nt':
            sig = os.path.expandvars('$USERPROFILE\\.signature')
        else:
            sig = os.path.expandvars('$HOME/.signature')
        if os.path.isfile(sig):
            return sig
        return ''

    sig = ''
    for t in to_name:
        sig = get_signature(t)
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


def get_config(config):
    """ get notmuch setting """
    db = notmuch2.Database()
    ret = db.config[config]
    db.close()
    return ret


def save_mail(msg_id, s, args):
    '''
    メール本文をテキスト・ファイルとして保存
    thread で複数選択時
        * do_mail() の繰り返しで一度処理すると
            - args[0], args[1] ファイル名未入力時キャンセル扱いの判定に使う為 -1 にする
            - args[2]          保存ファイルのベース名
            - args[3]          連番のためのカウンタ
            - args[4]          保存ファイルの拡張子
    '''
    def single_file():
        if len(args) >= 3:
            save_file = args[2]
            if os.path.isfile(save_file):
                if is_gtk():
                    over_write = vim_confirm('Overwrite?', 'Yes(&Y)\nNo(&N)', 1, 'Question')
                else:
                    over_write = vim_confirm('Overwrite?', '&Yes\n&No', 1, 'Question')
                if over_write != 1:
                    return ''
        else:
            save_file = get_save_filename(get_save_dir())
        return save_file

    def multi_file():
        if len(args) == 2:
            if use_browse():
                save_file = vim_browse(1, 'Save',
                                       os.path.dirname(get_save_dir()), '').decode()
            else:
                save_file = vim_input('Save as: ', get_save_dir(), 'file')
            if save_file == '':
                return ''
            args.extend(['', 2, ''])
            (args[2], args[4]) = os.path.splitext(save_file)
        else:
            args.extend([2, ''])
            (args[2], args[4]) = os.path.splitext(args[2])
        return args[2] + '-1' + args[4]

    global DBASE
    type = buf_kind()
    b = vim.current.buffer
    if type == 'show' or type == 'view':
        save_file = single_file()
        if save_file == '':
            return args
    elif args[0] == -1:
        print('No save.')
        return args
    else:
        if len(args) == 5:
            save_file = args[2] + '-' + str(args[3]) + args[4]
            args[3] += 1
        elif args[0] == args[1]:
            save_file = single_file()
            if save_file == '':
                print('No save.')
                return args
        else:
            save_file = multi_file()
            if save_file == '':
                return [-1, -1]
        if type == 'folders' or type == 'thread':
            buf_num = s_buf_num('show', '')
        elif type == 'search':
            buf_num = s_buf_num('view', b.vars.search_term)
        DBASE = notmuch2.Database(mode=notmuch2.Database.MODE.READ_WRITE)
        open_mail_by_msgid(s, msg_id, buf_num, False)
        DBASE.close()
    with open(save_file, 'w') as fp:
        fp.write('\n'.join(vim.current.buffer[:]))
    vim_goto_bufwinid(b.number)
    vim.command('redraw')
    print('save ' + save_file)
    return args


def move_mail(msg_id, s, args):
    """ move mail to other mbox """
    if args is None:  # 複数選択してフォルダを指定しなかった時の 2 つ目以降
        return
    if opened_mail(False):
        print_warring('Please save and close mail.')
        return
    mbox = args[2:]
    if not mbox:
        mbox.extend(vim_input_ls('Move Mail folder: ',
                                 '.' if get_mailbox_type() == 'Maildir' else '',
                                 'customlist,notmuch_py#CompDir'))
    if not mbox:
        return
    mbox = mbox[0]
    if mbox == '.':
        return
    db = notmuch2.Database()  # 呼び出し元で開く処理で書いてみたが、それだと複数メールの処理で落ちる
    msg = db.find(msg_id)
    tags = list(msg.tags)
    for f in msg.filenames():
        if os.path.isfile(f):
            move_mail_main(msg_id, f, mbox, [], tags, False)
        else:
            print('Already Delete: ' + str(f))
    db.close()
    reprint_folder2()  # 閉じた後でないと、メール・ファイル移動の情報がデータベースに更新されていないので、エラーになる
    return [1, 1, mbox]  # Notmuch mark-command (command_marked) から呼び出された時の為、リストで返す


def move_mail_main(msg_id, path, move_mbox, delete_tag, add_tag, draft):
    """ メール移動 """
    mailbox_type = get_mailbox_type()
    if mailbox_type == 'Maildir':
        if move_mbox[0] == '.':
            move_mbox = PATH + os.sep + move_mbox
        else:
            move_mbox = PATH + os.sep + '.' + move_mbox
        if os.path.dirname(os.path.dirname(path)) == move_mbox:  # 移動先同じ
            return
        save_path = move_mbox + os.sep + 'new'
        mbox = mailbox.Maildir(move_mbox)
    elif mailbox_type == 'MH':
        save_path = PATH + os.sep + move_mbox
        if os.path.dirname(os.path.dirname(path)) == save_path:  # 移動先同じ
            return
        mbox = mailbox.MH(save_path)
    else:
        print_err('Not support Mailbox type: ' + mailbox_type)
        return
    mbox.lock()
    msg_data = MIMEBase('text', 'plain')
    save_path += os.sep + str(mbox.add(msg_data))  # MH では返り値が int
    shutil.move(path, save_path)
    mbox.flush()
    mbox.unlock()
    # タグの付け直し
    if opened_mail(draft):
        print_warring('Can not update Notmuch database.\nPlease save and close mail.')
        return
    notmuch_new(False)
    msg = change_tags_before(msg_id)
    delete_tag += ['unread']  # mbox.add() は必ず unread になる
    with msg.frozen():
        delete_msg_tags(msg.tags, delete_tag)
        add_msg_tags(msg.tags, add_tag)  # 元々未読かもしれないので、追加を後に
    change_tags_after(msg, False)
    notmuch_new(False)
    vim.command('redraw')


def import_mail(args):
    if opened_mail(False):
        print_warring('Please save and close mail.')
        return
    import_dir = vim.vars.get('notmuch_import_mailbox', b'').decode()
    mailbox_type = get_mailbox_type()
    if import_dir == '':
        import_dir = PATH
    elif mailbox_type == 'Maildir':
        if import_dir[0] == '.':
            import_dir = PATH + os.sep + import_dir
        else:
            import_dir = PATH + os.sep + '.' + import_dir
    elif mailbox_type == 'MH':
        import_dir = PATH + os.sep + import_dir
    else:
        print_err('Not support Mailbox type: ' + mailbox_type)
        return
    make_dir(import_dir)
    if mailbox_type == 'Maildir':
        mbox = mailbox.Maildir(import_dir)
        make_dir(import_dir + os.sep + 'new')
        make_dir(import_dir + os.sep + 'cur')
        make_dir(import_dir + os.sep + 'tmp')
    elif mailbox_type == 'MH':
        mbox = mailbox.MH(import_dir)
    mbox.lock()
    if len(args) == 3:
        f = args[2]
    else:
        if os.name == 'nt':
            f = vim_input('Import: ', os.path.expandvars('$USERPROFILE\\'), 'file')
        else:
            f = vim_input('Import: ', os.path.expandvars('$HOME/'), 'file')
    if f == '':
        return
    if os.path.isdir(f):  # ディレクトリならサブ・ディレクトリまで含めてすべてのファイルを対象とする
        if f[-1] == os.sep:
            f = glob.glob(f + '**', recursive=True)
        else:
            f = glob.glob(f + os.sep + '**', recursive=True)
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
            print_warring('Import fail : ' + f)
            continue
        if msg_id[0] == '<' and msg_id[-1] == '>':
            msg_id = msg_id[1:-1]
        msg_ids.append(msg_id)
        mbox.add(msg)
    mbox.flush()
    mbox.unlock()
    # タグの付け直し
    notmuch_new(False)
    # db = notmuch2.Database(mode=notmuch2.Database.MODE.READ_WRITE)
    # for msg_id in msg_ids:
    #     msg = change_tags_before_core(msg_id)
    #     add_msg_tags(msg.tags, ['inbox'])
    #     change_tags_after_core(msg, True)
    # db.close()
    print_folder()
    vim.command('redraw')


def select_file(msg_id, question, s):
    """ get mail file list """
    def get_attach_info(f):
        with open(f, 'rb') as fp:
            msg = email.message_from_binary_file(fp)
        t = msg.get_content_subtype().lower()
        if t == 'encrypted' or t == 'pkcs7-mime':
            return '🔑'
        if not msg.is_multipart():
            return '📎0'
        count = 0
        if msg.get_content_type().lower() == 'text/html':
            html = '🌐'
        else:
            html = ''
        for part in msg.walk():
            if part.is_multipart():
                continue
            t = part.get_content_type().lower()
            if t == 'text/html' and (part.get_payload()):
                html = '🌐'
            elif t != 'text/plain' and t != 'text/html' and (part.get_payload()):
                count += 1
        return html + '📎' + str(count)

    if msg_id == '':
        msg_id = get_msg_id()
        if msg_id == '':
            return [], '', 0, ''
    dbase = notmuch2.Database()
    msg = dbase.find(msg_id)
    if msg is None:  # すでにファイルが削除されているとき
        print('The email has already been completely deleted.')
        dbase.close()
        return [], '', 0, ''
    try:
        subject = get_msg_header(open_email_file_from_msg(msg), 'Subject')
    except notmuch2.NullPointerError:  # すでにファイルが削除されているとき
        print('The email has already been completely deleted.')
        dbase.close()
        return [], '', 0, ''
    prefix = len(PATH) + 1
    files = []
    lst = ''
    size = 0
    len_i = 1
    for i, f in enumerate(msg.filenames()):  # ファイル・サイズの最大桁数の算出
        if os.path.isfile(f):
            len_i += 1
            f_size = os.path.getsize(f)
            if size < f_size:
                size = f_size
    size = len(str(size))
    len_i = len(str(len_i))
    for i, f in enumerate(msg.filenames()):
        f = str(f)
        if os.path.isfile(f):
            fmt = '{0:<' + str(len_i) + '}|{1}{2:<5}{3:>' + str(size) + '} B| {4}\n'
            attach = get_attach_info(f)
            date = datetime.datetime.fromtimestamp(os.path.getmtime(f))
            f_size = os.path.getsize(f)
            lst += fmt.format(
                str(i + 1),
                date.strftime(DATE_FORMAT),
                attach,
                str(f_size),
                f[prefix:])
            files.append({'name': f, 'date': date, 'size': int(f_size)})
        else:
            print_warring('Already Delete. ' + f[prefix:])
    dbase.close()
    if len(files) == 1:
        return files, subject, 1, ''
    i = i + 1
    while True:
        if s == '':
            s = vim_input(question + ' [1-' + str(i)
                          + ']/[N]ewest/[O]ldest/[B]iggest/[S]mallest/[A]ll/[Enter]:[C]ancel\n' + lst)
        if s == '':
            return [], '', 0, ''
        else:
            s = s[0]
        if s == 'C' or s == 'c':
            return [], '', 0, ''
        elif s == 'A' or s == 'a':
            return files, subject, -1, ''
        elif s == 'B' or s == 'b':
            return files, subject, [i for i, x in enumerate(files)
                                    if x['size'] == max([x['size'] for x in files])][0] + 1, 'B'
        elif s == 'S' or s == 's':
            return files, subject, [i for i, x in enumerate(files)
                                    if x['size'] == min([x['size'] for x in files])][0] + 1, 'S'
        elif s == 'N' or s == 'n':
            return files, subject, [i for i, x in enumerate(files)
                                    if x['date'] == max([x['date'] for x in files])][0] + 1, 'N'
        elif s == 'O' or s == 'o':
            return files, subject, [i for i, x in enumerate(files)
                                    if x['date'] == min([x['date'] for x in files])][0] + 1, 'O'
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
    return files, subject, s, ''


def is_draft():
    b = vim.current.buffer
    if b.options['filetype'] == b'notmuch-draft':
        if get_mailbox_type() == 'Maildir':
            draft_dir = PATH + os.sep + '.draft'
        else:
            draft_dir = PATH + os.sep + 'draft'
        if b.name.startswith(draft_dir + os.sep) \
                or 'draft' in b.vars['notmuch']['tags'].decode().split(' '):
            return True
    return False


def do_mail(cmd, args):
    """
    cmd:mail に対しての処理
    args:行番号などのコマンド引数
    folders では警告表示
    """
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
    if get_msg_id() == '':
        return
    if bnum == s_buf_num('thread', '') \
        or ((search_term in s_buf_num('search', ''))
            and bnum == s_buf_num('search', search_term)):
        args[0] = int(args[0])
        args[1] = int(args[1])
        for i in range(args[0], args[1] + 1):
            msg_id = THREAD_LISTS[search_term]['list'][i - 1]._msg_id
            args = cmd(msg_id, search_term, args)
    elif (('show' in s_buf_num_dic())
            and bnum == s_buf_num('show', '')) \
        or ((search_term in s_buf_num('view', ''))
            and bnum == s_buf_num('view', search_term)):
        args = cmd(b_v['msg_id'].decode(), search_term, args)


def delete_mail(msg_id, s, args):
    # s はダミー
    if len(args) > 2:
        key = args[2]
    else:
        key = ''
    files, tmp, num, key = select_file(msg_id, 'Except \'All\', leave selected file.\nselect file.', key)
    if not num:
        return [0, 0, key]
    if len(files) == 1:
        if is_gtk():
            s = vim_confirm('Delete ' + files[0]['name'] + '?', 'Yes(&Y)\nNo(&N)', 2, 'Question')
        else:
            s = vim_confirm('Delete ' + files[0]['name'] + '?', '&Yes\n&No', 2, 'Question')
        if s == 1:
            os.remove(files[0]['name'])
        return [0, 0, key]
    if num != -1:
        del files[num - 1]
    for f in files:
        os.remove(f['name'])
    if not notmuch_new(True):
        print_warring('Can\'t update database.')
    return [0, 0, key]


def export_mail(msg_id, s, args):
    #  s, args はダミー
    if len(args) > 2:
        key = args[2]
    else:
        key = ''
    files, subject, num, key = select_file(msg_id, 'Select export file', key)
    if not num:
        return [0, 0, key]
    s_dir = get_save_dir()
    subject = s_dir + re.sub(r'[\\/:\*\? "<>\|]', '-',
                             RE_TOP_SPACE.sub('', RE_END_SPACE.sub('', subject)))
    if num != -1:
        path = subject + '.eml'
        path = get_save_filename(path)
        if path != '':
            shutil.copyfile(files[num - 1]['name'], path)
        return [0, 0, key]
    for i, f in enumerate(files):
        if i:
            path = subject + '(' + str(i) + ').eml'
        else:
            path = subject + '.eml'
        path = get_save_filename(path)
        if path != '':
            shutil.copyfile(f['name'], path)
    return [0, 0, key]


def get_mail_subfolders(root, folder, lst):
    """ get sub-mailbox lists """
    path_len = len(PATH) + 1
    mailbox_type = get_mailbox_type()
    if mailbox_type == 'Maildir':
        folder = root + os.sep + '.' + folder
        mbox = mailbox.Maildir(folder)
    elif mailbox_type == 'MH':
        folder = root + os.sep + folder
        mbox = mailbox.MH(folder)
    else:
        # print_err('Not support Mailbox type: ' + mailbox_type)
        return []
    lst.append(folder[path_len:])
    for f in mbox.list_folders():
        get_mail_subfolders(folder, f, lst)


def get_mail_folders():
    """ get mailbox lists """
    mailbox_type = get_mailbox_type()
    if mailbox_type == 'Maildir':
        mbox = mailbox.Maildir(PATH)
        notmuch_cnf_dir = 'notmuch'
    elif mailbox_type == 'MH':
        mbox = mailbox.MH(PATH)
        notmuch_cnf_dir = '.notmuch'
    else:
        # print_err('Not support Mailbox type: ' + mailbox_type)
        return []
    lst = []
    for folder in mbox.list_folders():
        if folder != notmuch_cnf_dir:
            get_mail_subfolders(PATH, folder, lst)
    lst.sort()
    return lst


def run_shell_program(msg_id, s, args):
    def msg_file(msg):
        for f in msg.filenames():
            if os.path.isfile(f):
                return str(f)
        return None

    prg_param = args[2:]
    if not prg_param:
        prg_param = vim_input('Program and args: ', '', 'customlist,notmuch_py#CompRun')
        if prg_param == '':
            return
        else:
            prg_param = re.sub(
                ' +$', '', re.sub('^ +', '', prg_param)).split(' ')
    dbase = notmuch2.Database()
    msg = dbase.find(msg_id)
    if not ('<path:>' in prg_param) and not ('<id:>' in prg_param):
        f = msg_file(msg)
        if f is None:
            return
        while '<pipe:>' in prg_param:
            i = prg_param.index('<pipe:>')
            prg_param[i] = '|'
        prg_param.append(f)
    else:
        while '<path:>' in prg_param:
            i = prg_param.index('<path:>')
            f = msg_file(msg)
            if f is None:
                print_warring('Delte mail file.')
                return
            prg_param[i] = f
        while '<id:>' in prg_param:
            i = prg_param.index('<id:>')
            prg_param[i] = msg_id
        while '<pipe:>' in prg_param:
            i = prg_param.index('<pipe:>')
            prg_param[i] = '|'
    dbase.close()
    shellcmd_popen(prg_param)
    print(' '.join(prg_param))
    return [0, 0, prg_param]


def get_cmd_name_ftype():
    """ バッファの種類による処理できるコマンド・リスト """
    if vim.current.buffer.options['filetype'] == b'notmuch-edit':
        return []
    cmd_dic = []
    cmds = vim.vars['notmuch_command']
    if vim.current.buffer.options['filetype'] == b'notmuch-draft':
        for cmd, v in cmds.items():
            if v[1] & 0x08:
                cmd_dic.append(cmd.decode())
    else:
        for cmd, v in cmds.items():
            if v[1] & 0x04:
                cmd_dic.append(cmd.decode())
    return sorted(cmd_dic, key=str.lower)


def get_command():
    """ マークしたメールを纏めて処理できるコマンド・リスト (subcommand: executable) """
    cmd_dic = {}
    cmds = vim.vars['notmuch_command']
    for cmd, v in cmds.items():
        cmd = cmd.decode()
        if v[1] & 0x02:
            cmd_dic[cmd] = v[1]
    return cmd_dic


def get_cmd_name():
    """ コマンド名リスト """
    return sorted([b.decode() for b in vim.vars['notmuch_command'].keys()], key=str.lower)


def get_mark_cmd_name():
    """ マークしたメールを纏めて処理できるコマンド名リスト """
    return sorted(list(get_command().keys()), key=str.lower)


def get_last_cmd(cmds, cmdline, pos):
    """ コマンド列から最後のコマンドと引数が有るか? を返す """
    regex = ' (' + '|'.join(cmds) + ') '
    result = list(re.finditer(regex, cmdline[:pos], flags=re.MULTILINE))
    if result == []:
        return []
    result = result[-1]
    last_str = cmdline[result.span()[1]:]
    # last_str = re.sub(r'^\s+', '', last_str)
    last_str = RE_TOP_SPACE.sub('', re.sub(r'\s+', ' ', last_str, flags=re.MULTILINE))
    return [result.group(1), ' ' in last_str]
    # 最後のコマンドより後ろで、それに続く空白を削除してなおどこかに空白が有れば引数を指定済み


def command_marked(cmdline):
    b = vim.current.buffer
    try:
        search_term = b.vars['notmuch']['search_term'].decode()
    except KeyError:
        print_warring('Don\'t open mail or is done with \'folders\'.')
        return
    if b.number != s_buf_num('thread', '') \
            and not (search_term in s_buf_num('search', '')) \
            and b.number != s_buf_num('search', search_term):
        print_warring('The command can only be used on thread/search.')
        return
    if b[0] == '':
        return
    marked_line = get_mark_in_thread()
    if marked_line == []:
        print_warring('Mark the email that you want to command. (:Notmuch mark)')
        return
    if not cmdline:
        cmdline.extend(vim_input_ls('Command: ', '', 'customlist,notmuch_py#CompCmd'))
    if not cmdline:
        return
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
        if arg not in cmds:
            print_warring('Error: ' + arg + ' do not exist in sub-command.')
            continue
        if cmd == '' and (cmds[arg] & 0x02):  # 引数必要
            cmd = arg
        elif cmd == '' and (cmds[arg] & 0x02):  # 引数を必要としないコマンド
            cmd_arg.append([cmds_dic[arg][0].decode(), ''])
            cmd = ''
        elif arg == '\r' or arg == '\x00':  # コマンド区切り
            if cmd != '':
                cmd_arg.append([cmds_dic[cmd][0].decode(), args])
                cmd = ''
                args = []
        else:  # コマンド引数
            args.append(arg)
    if cmd != '':
        cmd_arg.append([cmds_dic[cmd][0].decode(), args])
    # 実際にここのメールにコマンド実行
    vim2PyCmd = {
        'AddTags': 'add_tags',
        'DeleteTags': 'delete_tags',
        'SetTags': 'set_tags',
        'ToggleTags': 'toggle_tags',
        'DeleteMail': 'delete_mail',
        'ExportMail': 'export_mail',
        'MoveMail': 'move_mail',
        'OpenOriginal': 'edit_mail',
        'ReindexMail': 'reindex_mail',
        'RunShellProgram': 'run_shell_program',
        'DeleteAttachment': 'delete_attachment',
        'SaveAttachment': 'save_attachment',
        'ConnectThread': 'connect_thread_tree',
        'CutThread': 'cut_thread',
    }
    for i, cmd in enumerate(cmd_arg):
        for line in marked_line:
            py_cmd = vim2PyCmd[cmd[0]]
            msg_id = THREAD_LISTS[search_term]['list'][line]._msg_id
            if py_cmd in [  # 複数選択対応で do_mail() から呼び出されるものは search_term が必要
                # 不要な場合はダミーの文字列
                'add_tags',
                'set_tags',
                'delete_mail',
                'delete_tags',
                'export_mail',
                'move_mail',
                'open_original',
                'reindex_mail',
                'run_shell_program',
                'toggle_tags',
            ]:
                args = (GLOBALS[py_cmd](msg_id, search_term, [line, line] + cmd[1]))[2:]
            else:
                args = GLOBALS[py_cmd](msg_id, cmd[1])
            cmd_arg[i][1] = args  # 引数が空の場合があるので実行した引数で置き換え
    vim_sign_unplace('')
    # DBASE = notmuch2.Database()
    reprint_folder2()
    # DBASE.close()


def notmuch_search(search_term):
    i_search_term = ''
    search_term = search_term[2:]
    if search_term == '' or search_term == []:  # コマンド空
        if vim.current.buffer.number == s_buf_num('folders', ''):
            i_search_term = vim.vars['notmuch_folders'][vim.current.window.cursor[0] - 1][1].decode()
        else:
            i_search_term = vim.current.buffer.vars['notmuch']['search_term'].decode()
        search_term = vim_input('search term: ', i_search_term, 'customlist,notmuch_py#CompSearch')
        if search_term == '':
            return
    elif type(search_term) is list:
        search_term = ' '.join(search_term)
    if not check_search_term(search_term):
        return
    db = notmuch2.Database()
    search_term = RE_END_SPACE.sub('', search_term)
    if search_term == i_search_term:
        if vim.current.buffer.number == s_buf_num('folders', ''):
            if search_term == \
                    vim.buffers[s_buf_num('thread', '')].vars['notmuch']['search_term'].decode():
                vim_goto_bufwinid(s_buf_num("thread", ''))
            else:
                open_thread(vim.current.window.cursor[0], True, False)
                if vim.current.buffer[0] != '' and is_same_tabpage('show', ''):
                    open_mail_by_index(search_term,
                                       vim.windows[s_buf_num('thread', '')].cursor[0] - 1,
                                       vim.buffers[s_buf_num('thread', '')].number)
        return
    try:
        if db.count_messages(search_term) == 0:
            db.close()
            print_warring('Don\'t find mail.  (0 search mail).')
            return
    except notmuch2.XapianError:
        db.close()
        vim.command('redraw')
        print_error('notmuch2.XapianError: Check search term: ' + search_term + '.')
        return
    db.close()
    vim.command('MakeSearchList(\'' + vim_escape(search_term) + '\')')
    b_num = s_buf_num('search', search_term)
    print_thread(b_num, search_term, False, False)
    if is_same_tabpage('view', search_term):
        open_mail()


def notmuch_thread():
    global DBASE
    msg_id = get_msg_id()
    if msg_id == '':
        return
    DBASE = notmuch2.Database()
    thread_id = 'thread:' + DBASE.find(msg_id).threadid
    DBASE.close()
    notmuch_search([0, 0, thread_id])  # 先頭2つの0はダミーデータ
    fold_open_core()
    index = [i for i, msg in enumerate(
        THREAD_LISTS[thread_id]['list']) if msg._msg_id == msg_id]
    b = vim.current.buffer
    if not index:  # 一度スレッド検索後、同じスレッドで受信したメールに対してスレッド検索
        notmuch_new(False)
        DBASE = notmuch2.Database()
        print_thread_core(b.number, thread_id, False, True)
        DBASE.close()
        fold_open_core()
        index = [i for i, msg in enumerate(
            THREAD_LISTS[thread_id]['list']) if msg._msg_id == msg_id]
    index = index[0] + 1
    if len(b) != len(THREAD_LISTS[thread_id]['list']):
        DBASE = notmuch2.Database()
        print_thread_core(b.number, thread_id, False, True)
        DBASE.close()
        fold_open_core()
    reset_cursor_position(b, index)


def notmuch_address():
    def only_address(address):
        ls = []
        for i in address:
            only_adr = email2only_address(i).lower()
            if only_adr != '':
                ls.append(only_adr)
        return ls

    msg_id = get_msg_id()
    if msg_id == '':
        return
    dbase = notmuch2.Database()
    msg = dbase.find(msg_id)
    if msg is None:
        print_error('Email data has been deleted.')
        return
    msg_f = open_email_file_from_msg(msg)
    if vim.vars['notmuch_sent_tag'].decode() in list(msg.tags):
        adr = only_address(address2ls(get_msg_header(msg_f, 'To')))
        if not adr:
            adr = only_address(address2ls(get_msg_header(msg_f, 'Cc')))
            if not adr:
                adr = only_address(address2ls(get_msg_header(msg_f, 'Bcc')))
    else:
        adr = only_address(address2ls(msg.header('From'))) + \
            only_address(address2ls(get_msg_header(msg_f, 'Reply-To')))
    dbase.close()
    if not adr:
        if vim.vars['notmuch_sent_tag'].decode() in msg.tags:
            print_warring('To/Cc/Bcc header is empty.')
        else:
            print_warring('From header is empty.')
        return
    search_term = ''
    for i in set(adr):
        search_term += ' or from:' + i + ' or to:' + i
    search_term = search_term[4:]
    notmuch_search([0, 0, search_term])  # 先頭2つの0はダミーデータ
    fold_open_core()
    index = [i for i, msg in enumerate(
        THREAD_LISTS[search_term]['list']) if msg._msg_id == msg_id]
    reset_cursor_position(vim.current.buffer, index[0] + 1)


def notmuch_duplication(remake):
    set_global_var()
    if remake or not ('*' in THREAD_LISTS):
        db = notmuch2.Database()
        # THREAD_LISTS の作成はマルチプロセスも試したが、大抵は数が少ないために反って遅くなる
        ls = []
        for msg in db.messages('path:**'):
            if len(list(msg.filenames())) >= 2:
                thread = next(db.threads('thread:' + msg.threadid))  # threadid で検索しているので元々該当するのは一つ
                ls.append(MailData(msg, thread, 0, 0))
        db.close()
        if not ls:
            print_warring('Don\'t duple mail.')
            return
        ls.sort(key=attrgetter('_date', '_from'))
        THREAD_LISTS['*'] = {'list': ls, 'sort': ['date', 'list']}
    vim.command('MakeSearchList(\'*\')')
    b_num = s_buf_num('search', '*')
    print_thread(b_num, '*', False, False)
    if is_same_tabpage('view', '*'):
        open_mail()


def check_search_term(s):
    if s == '*':
        print_warring('Error: When you want to search all mail, use \'path:**\'.')
        return False
    elif len(re.sub(r'[^"]', '', s.replace(r'\\', '').replace(r'\"', ''))) % 2:
        print_warring('Error: \'"\' (double quotes) is not pair.')
        return False
    bra = len(re.sub(r'[^(]', '', s.replace(r'\\', '').replace(r'\(', '')))
    cket = len(re.sub(r'[^)]', '', s.replace(r'\\', '').replace(r'\)', '')))
    if bra != cket:
        print_warring('Error: \'()\', round bracket is not pair.')
        return False
    return True


def set_header(b, i, s):
    """ バッファ b の i 行が空行なら s を追加し、空行でなければ s に置き換える """
    if b[i] == '':
        b.append(s, i)
    else:
        b[i] = s


def delete_header(b, h):
    i = 0
    for s in b:
        if s.lower().startswith(h):
            b[i] = None
        i += 1


def set_fcc(args):
    if not is_draft():
        return
    b = vim.current.buffer
    if get_mail_folders() == 'Maildir':  # 入力初期値に先頭「.」付加
        fcc = '.'
    else:
        fcc = ''
    i = 0
    for s in b:
        if s.lower().startswith('fcc:'):
            if fcc == '' or fcc == '.':
                match = re.match(r'^Fcc:\s*', s, re.IGNORECASE)
                fcc = s[match.end():]
            else:  # 複数有った時は 2 つ目以降削除
                b[i] = None
        elif s == '':
            break
        i += 1
    mbox = args[2:]
    if not mbox:
        mbox.extend(vim_input_ls('Save Mail folder: ', fcc, 'customlist,notmuch_py#CompDir'))
    if not mbox:
        delete_header(b, 'fcc')
    else:
        mbox = mbox[0]
        if mbox == '' or mbox == '.':
            delete_header(b, 'fcc')
        else:
            i = 0
            for s in b:
                if s.lower().startswith('fcc:') or s == '':
                    break
                i += 1
            set_header(b, i, 'Fcc: ' + mbox)


def set_attach(args):
    if not is_draft():
        return
    attach = args[2:]
    b = vim.current.buffer
    l_attach = vim.current.window.cursor[0] - 1
    h_last = 0
    for s in b:
        if s == '':
            break
        h_last += 1
    if h_last < l_attach:
        l_attach = -1
    if os.name == 'nt':
        home = os.path.expandvars('$USERPROFILE\\')
    else:
        home = os.path.expandvars('$HOME/')
    while True:
        if use_browse():
            if attach == []:
                attach = vim_browse(0, 'select attachment file', home, '').decode()
                if attach == '':
                    return
        else:
            if not attach:
                attach.extend(vim_input_ls('Select Attach: ', home, 'file'))
            if not attach:
                return
            attach = attach[0]
        attach = os.path.expanduser(os.path.expandvars(attach))
        if not os.path.exists(attach):
            print_error('Not exist: ' + attach)
        elif os.path.isdir(attach):
            print_error('Directory: ' + attach)
        elif os.access(attach, os.R_OK):
            break
        else:
            print_error('Do not read: ' + attach)
    for s in b:
        match = re.match(r'^Attach:\s*', s)
        if match is not None:
            if os.path.expanduser(os.path.expandvars(s[match.end():])) == attach:
                return
    if l_attach >= 0 and b[l_attach].lower().startswith('attach:'):
        b[l_attach] = 'Attach: ' + attach
        return
    while h_last >= 0:  # 空の Attach ヘッダ削除
        if re.match(r'^Attach:\s*$', b[h_last]):
            b[h_last] = None
        h_last -= 1
    i = 0
    l_attach = -1
    for s in b:
        if s.lower().startswith('attach:'):
            l_attach = i
        if s == '':
            break
        i += 1
    b.append('Attach: ' + attach, i)


def use_browse():
    return vim_has('browse') \
        and (not ('notmuch_use_commandline' in vim.vars) or vim.vars['notmuch_use_commandline'] == 0)


def set_encrypt(args):
    ENCRYPT = 0x01
    SIGNATURE = 0x02
    PGP = 0x10
    PGPMIME = 0x20
    PGPMIME_ENCRYPT = PGPMIME | ENCRYPT
    SMIME = 0x40
    SUBJECT = 0x100
    PUBLIC = 0x200
    if not is_draft():
        return
    encrypt = []
    for i in args[2:]:
        encrypt.append(i.lower())
    b = vim.current.buffer
    flag = 0
    h_last = 0
    for s in b:
        match = re.match(r'^(Encrypt|Signature):\s*', s, flags=re.IGNORECASE)
        if s == '':
            break
        h_last += 1
        if match is None:
            continue
        h_term = s[:s.find(':')].lower()
        h_item = s[match.end():]
        if h_term == 'encrypt':
            flag = flag | ENCRYPT \
                | (get_flag(h_item, r'\bS[/-]?MIME\b') * SMIME) \
                | (get_flag(h_item, r'\bPGP\b') * PGP) \
                | (get_flag(h_item, r'\bPGP[/-]?MIME\b') * PGPMIME) \
                | (get_flag(h_item, r'\bSubject\b') * SUBJECT) \
                | (get_flag(h_item, r'\bPublic-?Key\b') * PUBLIC)
        elif h_term == 'signature':
            flag = flag | SIGNATURE \
                | (get_flag(h_item, r'\bS[/-]?MIME\b') * SMIME) \
                | (get_flag(h_item, r'\bPGP\b') * PGP) \
                | (get_flag(h_item, r'\bPGP[/-]?MIME\b') * PGPMIME)
    if encrypt != []:
        if 'encrypt' in encrypt:
            flag = ENCRYPT
        else:
            flag = 0
        if 'signature' in encrypt:
            flag = flag | SIGNATURE
        if ('s/mime' in encrypt) or ('s-mime' in encrypt) or ('smime' in encrypt):
            flag = flag | SMIME
        elif ('pgp/mime' in encrypt) or ('pgp-mime' in encrypt) or ('pgpmime' in encrypt):
            flag = flag | PGPMIME
        elif 'pgp' in encrypt:
            flag = flag | PGP
        else:
            flag = flag | SMIME
        if 'subject' in encrypt:
            flag = flag | SUBJECT
        if 'signature' in encrypt:
            flag = flag | PUBLIC
    else:
        # 暗号化・署名が複数指定されていた時、暗号化と署名方法に矛盾していた時のために flag を指定し直す
        if flag & SMIME:
            flag = flag & ~(PGP | PGPMIME)
        elif flag & PGPMIME:
            flag = flag & ~PGP
        while True:
            if flag & ENCRYPT:
                encrypt = 'ON'
            else:
                encrypt = 'OFF'
            if flag & SIGNATURE:
                signature = 'ON'
            else:
                signature = 'OFF'
            if flag & SMIME:
                method = 'S/MIME'
            elif flag & PGPMIME:
                method = 'PGP/MIME'
            elif flag & PGP:
                method = 'PGP'
            else:
                flag |= SMIME
                method = 'S/MIME'
            if flag & SUBJECT:
                subject = 'ON'
            else:
                subject = 'OFF'
            if flag & PUBLIC:
                public_key = 'ON'
            else:
                public_key = 'OFF'
            if (flag & PGPMIME_ENCRYPT) == PGPMIME_ENCRYPT:
                applies = vim_confirm('Encrypt: ' + encrypt
                                      + ' | Signature: ' + signature
                                      + ' | Method: ' + method
                                      + '\nSubject : ' + subject
                                      + ' | Public Key: ' + public_key,
                                      '&Encrypt\n&Digital Signature\n&Method\n&Subject\n&Public Key\n&Apply',
                                      6, 'Question')
            else:
                applies = vim_confirm('Encrypt: ' + encrypt
                                      + ' | Signature: ' + signature
                                      + ' | Method: ' + method,
                                      '&Encrypt\n&Digital Signature\n&Method\n&Apply', 4, 'Question')
            if applies == 0 or applies == b'':
                return
            elif applies == 1 or applies == b'E' or applies == b'e':
                flag ^= ENCRYPT
            elif applies == 2 or applies == b'D' or applies == b'd':
                flag ^= SIGNATURE
            elif applies == 3 or applies == b'M' or applies == b'm':
                if flag & SMIME:
                    flag = flag ^ SMIME | PGPMIME
                elif flag & PGPMIME:
                    flag = flag ^ PGPMIME | PGP
                else:  # 暗号化と署名が両方無ければ、暗号化方式の意味がないので、全て OFF への切り替えは無くても良い
                    flag = flag ^ PGP | SMIME
            elif applies == 4:
                if (flag & PGPMIME_ENCRYPT) == PGPMIME_ENCRYPT:
                    flag ^= SUBJECT
                else:
                    break
            elif applies == b'S' or applies == b's':
                flag ^= SUBJECT
            elif applies == 5 or applies == b'P' or applies == b'p':
                flag ^= PUBLIC
            elif applies == 6 or applies == b'A' or applies == b'a':
                break
    l_encrypt = h_last
    while h_last >= 0:  # 全ての Encrypt/Signature ヘッダ削除と Encrypt/Signature が最初に有った位置の取得
        if re.match(r'^(Encrypt|Signature):', b[h_last]):
            l_encrypt = h_last
            b[h_last] = None
        h_last -= 1
    if flag & SIGNATURE:
        if flag & SMIME:
            b.append('Signature: S/MIME', l_encrypt)
        elif flag & PGPMIME:
            b.append('Signature: PGP/MIME', l_encrypt)
        else:
            b.append('Signature: PGP', l_encrypt)
    if flag & ENCRYPT:
        if flag & SMIME:
            b.append('Encrypt: S/MIME', l_encrypt)
        elif flag & PGPMIME:
            encrypt = 'Encrypt: PGP/MIME'
            if flag & SUBJECT:
                encrypt += ' Subject'
            if flag & PUBLIC:
                encrypt += ' Public-Key'
            b.append(encrypt, l_encrypt)
        else:
            b.append('Encrypt: PGP', l_encrypt)


def notmuch_refine(args):
    b = vim.current.buffer
    if b.number == s_buf_num('folders', ''):
        return
    b_v = b.vars
    if not ('search_term' in b_v['notmuch']):
        return
    b_v = b_v['notmuch']
    search_term = b_v['search_term'].decode()
    if search_term == '':
        return
    if args == '':  # コマンド空
        args = vim_input('search term: ', '', 'customlist,notmuch_py#CompSearch')
        if args == '':
            return
    if not check_search_term(args):
        return
    vim.command('refined_search_term = \'' + vim_escape(args) + '\'')
    notmuch_down_refine()


def get_refine_index():
    b = vim.current.buffer
    b_num = b.number
    if b_num == s_buf_num('folders', ''):
        return -1, '', []
    b_v = b.vars
    if not ('search_term' in b_v['notmuch']):
        return -1, '', []
    search_term = b_v['notmuch']['search_term'].decode()
    if search_term == '':
        return -1, '', []
    if b_num != s_buf_num('thread', '') \
        and b_num != s_buf_num('show', '') \
        and not (search_term in s_buf_num('search', '')
                 and b_num != s_buf_num('search', search_term)) \
        and not (search_term in s_buf_num('view', '')
                 and b_num != s_buf_num('view', search_term)):
        return -1, '', []
    if vim.bindeval('refined_search_term') == b'':
        print_warring('Do not execute \'search-refine\'')
        return -1, '', []
    msg_id = get_msg_id()
    dbase = notmuch2.Database()
    index = [i for i, msg in enumerate(THREAD_LISTS[search_term]['list'])
             if dbase.count_messages('id:"' + msg._msg_id + '" and ('
                                     + vim.bindeval('refined_search_term').decode() + ')')]
    if not index:
        return -1, '', []
    dbase.close()
    return [i for i, msg in enumerate(
            THREAD_LISTS[search_term]['list']) if msg._msg_id == msg_id][0], \
        search_term, index


def notmuch_refine_common(s, index):
    global DBASE
    org_b_num = vim.current.buffer.number
    b_num = org_b_num
    f_show = False
    if org_b_num == s_buf_num('show', ''):
        b_num = s_buf_num('thread', '')
        f_show = True
    elif s in s_buf_num('view', '') \
            and org_b_num == s_buf_num('view', s):
        b_num = s_buf_num('thread', s)
        f_show = True
    for b in vim.buffers:
        if b.number == b_num:
            break
    reset_cursor_position(b, index + 1)
    if (is_same_tabpage('thread', '') or is_same_tabpage('search', s)):
        vim_goto_bufwinid(b.number)
        fold_open()
    if f_show:
        DBASE = notmuch2.Database(mode=notmuch2.Database.MODE.READ_WRITE)
        msg_id = THREAD_LISTS[s]['list'][index]._msg_id
        open_mail_by_msgid(s, msg_id, str(org_b_num), True)
        DBASE.close()


def notmuch_down_refine():
    current_l, search_term, refine = get_refine_index()
    if current_l < 0:
        return
    index = [i for i in refine if i > current_l]
    if index:
        notmuch_refine_common(search_term, index[0])
    elif vim.options['wrapscan']:
        notmuch_refine_common(search_term, refine[0])


def notmuch_up_refine():
    current_l, search_term, refine = get_refine_index()
    if current_l < 0:
        return
    index = [i for i in refine if i < current_l]
    if index:
        notmuch_refine_common(search_term, index[-1])
    elif vim.options['wrapscan']:
        notmuch_refine_common(search_term, refine[-1])


def get_sys_command(cmdline, last):
    """ コマンドもしくは run コマンドで用いる <path:>, <id:> を返す """
    # シェルのビルトインは非対応
    def sub_path():
        path = set()
        if last == '' or (not os.path.isdir(last)) or last[-1] == os.sep:
            f = glob.glob(last + '*')
        else:
            f = glob.glob(last + os.sep + '*')
        for c in f:
            if os.path.isdir(c):
                path.add(c + os.sep)
            else:
                path.add(c)
        return path

    def get_cmd():
        cmd = set()
        for p in os.environ.get('path',
                                os.environ.get('PATH', [])).split(os.pathsep):
            if p[-1] == os.sep:
                f = glob.glob(p + '*')
            else:
                f = glob.glob(p + os.sep + '*')
            for c in f:
                cmd.add(os.path.basename(c))
        for c in sub_path():
            if os.path.isfile(c):
                if os.access(c, os.X_OK):
                    cmd.add(c)
            elif os.path.isdir(c):
                cmd.add(c)
        return cmd

    num = len(cmdline.split())
    if (num >= 3
            and re.search(r'(<pipe:><pipe:>|<pipe:>|&&|;) *$', cmdline) is not None):
        cmd = get_cmd()
    elif num > 3 or (num >= 3 and last == ''):
        cmd = {'<path:>', '<id:>', '<pipe:>'} | sub_path()
    else:
        cmd = get_cmd()
    return sorted(list(cmd))


def get_folded_list(start, end):
    search_term = vim.current.buffer.vars['notmuch']['search_term'].decode()
    if search_term == '':
        return ''
    msg = THREAD_LISTS[search_term]['list'][start - 1]
    line = msg.get_folded_list().replace('\u200B', '      ')
    tags = copy.copy(msg._tags)
    while start < end:
        tags += THREAD_LISTS[search_term]['list'][start]._tags
        start += 1
    emoji_tags = ''
    for t, emoji in {'unread': '📩', 'draft': '📝', 'flagged': '⭐',
                     'Trash': '🗑', 'attachment': '📎'}.items():
        if t in tags:
            emoji_tags += emoji
    emoji_tags = emoji_tags[:3]
    emoji_length = 6 - vim_strdisplaywidth(emoji_tags)
    # ↑基本的には unread, draft の両方が付くことはないので最大3つの絵文字
    if emoji_length:
        emoji_length = '{:' + str(emoji_length) + 's}'
        emoji_tags += emoji_length.format('')
    if ('notmuch_visible_line' in vim.vars):
        if ((vim.vars['notmuch_visible_line'] == 1 or vim.vars['notmuch_visible_line'] == 2)):
            return emoji_tags + line
        elif vim.vars['notmuch_visible_line'] == 3:
            return (emoji_tags + line).replace('\t', '│')
    return (emoji_tags + line).replace('\t', '|')


def buf_kind():
    """ カレント・バッファの種類 """
    # notmuch 関連以外は空文字
    # notmuch-edit, notmuch-draft は filetype で判定
    def for_filetype():
        ftype = b.options['filetype']
        if ftype == b'notmuch-edit':
            return 'edit'
        elif ftype == b'notmuch-draft':
            return 'draft'
        return ''

    b = vim.current.buffer
    b_num = b.number
    buf_num = s_buf_num_dic()
    if not ('folders' in buf_num) \
            or not ('folders' in buf_num) \
            or not ('folders' in buf_num):
        return for_filetype()
    if b_num == buf_num['folders']:
        return 'folders'
    elif 'thread' in buf_num and b_num == buf_num['thread']:
        return 'thread'
    elif 'show' in buf_num and b_num == buf_num['show']:
        return 'show'
    elif 'search' in buf_num and b_num in buf_num['search'].values():
        return 'search'
    elif 'view' in buf_num and b_num in buf_num['view'].values():
        return 'view'
    else:
        return for_filetype()


def get_hide_header():
    """
    メールファイルを開いた時に折り畳み対象となるヘッダの Vim の正規表現生成
    一般的なヘッダから g:notmuch_show_headers は除く
    ただし X- で始まるヘッダは常に折り畳み対象
    """
    hide = [
        'accept-language',
        'alternate-recipient',
        'approved',
        'approved-by',
        'archived-at',
        'authentication-results',
        'autoforwarded',
        'autosubmitted',
        'bcc',
        'cc',
        'comments',
        'content-alternative',
        'content-base',
        'content-charset',
        'content-convert',
        'content-description',
        'content-disposition',
        'content-duration',
        'content-encoding',
        'content-features',
        'content-id',
        'content-identifier',
        'content-language',
        'content-length',
        'content-location',
        'content-md5',
        'content-previous',
        'content-range',
        'content-return',
        'content-script-type',
        'content-style-type',
        'content-transfer-encoding',
        'content-type',
        'content-version',
        'content-x-properties',
        'conversion',
        'conversion-with-loss',
        'date',
        'dcc',
        'deferred-delivery',
        'delivered-to',
        'delivery-date',
        'discarded-x400-ipms-extensions',
        'discarded-x400-mts-extensions',
        'disclose-recipients',
        'disposition-notification-options',
        'disposition-notification-to',
        'dkim-signature',
        'dl-expansion-history',
        'domainkey-signature',
        'encoding',
        'encrypted',
        'envelope-to',
        'errors-to',
        'expires',
        'expiry-date',
        'face',
        'fcc',
        'feedback-id',
        'from',
        'generate-delivery-report',
        'importance',
        'in-reply-to',
        'incomplete-copy',
        'keywords',
        'language',
        'latest-delivery-time',
        'lines',
        'link',
        'list-archive',
        'list-help',
        'list-id',
        'list-owner',
        'list-post',
        'list-subscribe',
        'list-unsubscribe',
        'mail-followup-to',
        'mail-from',
        'mail-reply-to',
        'mailing-list',
        'message-context',
        'message-id',
        'message-type',
        'mime-version',
        'nntp-posting-date',
        'nntp-posting-host',
        'obsoletes',
        'old-return-path',
        'organization',
        'original-encoded-information-types',
        'original-message-id',
        'original-receipient',
        'original-received',
        'original-sender',
        'original-to',
        'original-x-from',
        'originator-return-address',
        'pics-label',
        'precedence',
        'prevent-nondelivery-report',
        'priority',
        'received',
        'references',
        'reply-by',
        'reply-to',
        'resent-bcc',
        'resent-cc',
        'resent-date',
        'resent-dcc',
        'resent-fcc',
        'resent-from',
        'resent-message-id',
        'resent-reply-to',
        'resent-sender',
        'resent-to',
        'return-path',
        'return-receipt-to',
        'sender',
        'sensitivity',
        'snapshot-content-location',
        'solicitation',
        'status',
        'subject',
        'supersedes',
        'to',
        'transport-options',
        'user-agent',
        r'x-[a-z-]\+',
        'x400-content-identifier',
        'x400-content-return',
        'x400-content-type',
        'x400-mts-identifier',
        'x400-originator',
        'x400-received',
        'x400-recipients',
        'x400-trace',
        'xref'
    ]
    for h in vim.vars['notmuch_show_headers']:
        h = h.decode().lower()
        if h in hide:
            hide.remove(h)
        if h in hide:
            hide.remove(h)
    return r'\|'.join(hide)


class notmuchVimError(Exception):
    """ 例外エラーを発生させる """
    pass


def set_defaults():
    if 'notmuch_folders' not in vim.vars:
        vim.vars['notmuch_folders'] = [
            ['new', '(tag:inbox and tag:unread)'],
            ['inbox', '(tag:inbox)'],
            ['unread', '(tag:unread)'],
            ['draft',
                '((folder:draft or folder:.draft or tag:draft) not tag:sent not tag:Trash not tag:Spam)'],
            ['attach', '(tag:attachment)'],
            ['6 month', '(date:183days..now'],
            ['', ''],
            ['All', '(folder:/./)'],
            ['Trash', '(folder:.Trash or folder:Trash or tag:Trash)'],
            ['New Search', ''],
        ]
    if 'notmuch_show_headers' not in vim.vars:
        vim.vars['notmuch_show_headers'] = [
            'From',
            'Resent-From',
            'Subject',
            'Date',
            'Resent-Date',
            'To',
            'Resent-To',
            'Cc',
            'Resent-Cc',
            'Bcc',
            'Resent-Bcc',
        ]
    if 'notmuch_show_hide_headers' not in vim.vars:
        vim.vars['notmuch_show_hide_headers'] = [
            'Return-Path',
            'Reply-To',
            'Message-ID',
            'Resent-Message-ID',
            'In-Reply-To',
            'References',
            'Errors-To',
        ]
        # 何故か Content-Type, Content-Transfer-Encoding は取得できない
    # g:notmuch_show_headers 登録済み、virtual ヘッダは除く
    hide_headers = list(vim.vars['notmuch_show_hide_headers'])
    for h in list(vim.vars['notmuch_show_headers']) \
            + [b'Attach', b'Decrypted', b'Encrypt', b'Fcc', b'HTML', b'Signature']:
        h = h.decode().lower()
        for i, j in enumerate(hide_headers):
            if h == j.decode().lower():
                hide_headers.pop(i)
    vim.vars['notmuch_show_hide_headers'] = hide_headers
    if 'notmuch_draft_header' not in vim.vars:
        vim.vars['notmuch_draft_header'] = ['From', 'To', 'Cc', 'Bcc', 'Subject', 'Reply-To', 'Attach']
    if 'notmuch_send_param' not in vim.vars:
        vim.vars['notmuch_send_param'] = ['sendmail', '-t', '-oi']
    if 'notmuch_sent_tag' not in vim.vars:  # 送信済みを表すタグ
        vim.vars['notmuch_sent_tag'] = 'sent'
    if 'notmuch_display_item' not in vim.vars:
        vim.vars['notmuch_display_item'] = ['subject', 'from', 'date']
    # OS 依存
    if 'notmuch_view_attachment' not in vim.vars:
        if sys.platform == 'darwin':  # macOS (os.name は posix)
            vim.vars['notmuch_view_attachment'] = 'open'
        elif os.name == 'posix':
            vim.vars['notmuch_view_attachment'] = 'xdg-open'
        elif os.name == 'nt':
            vim.vars['notmuch_view_attachment'] = 'start'
        else:
            vim.vars['notmuch_view_attachment'] = ''


def get_mailbox_type():
    """ Mailbox の種類 """
    if 'notmuch_mailbox_type' in vim.vars:
        return vim.vars['notmuch_mailbox_type'].decode()
    else:
        return 'Maildir'


def get_attach_dir():
    """ 添付ファイルを処理するディレクトリの種類 """
    if 'notmuch_attachment_tmpdir' in vim.vars:
        return os.path.expandvars(
            os.path.expanduser(
                vim.vars['notmuch_attachment_tmpdir'].decode()) + os.sep + 'attach' + os.sep)
    else:
        return script_root() + os.sep + 'attach' + os.sep


def get_temp_dir():
    """
    一次処理に用いるディレクトリの種類
    添付ファイルの一時展開先等 plugin/autoload ディレクトリに *.vim/*.py があるのでその親ディレクトリ
    """
    if 'notmuch_tmpdir' in vim.vars:
        return os.path.expandvars(
            os.path.expanduser(
                vim.vars['notmuch_tmpdir'].decode()) + os.sep + '.temp' + os.sep)
    else:
        return script_root() + os.sep + '.temp' + os.sep


#  以下初期化処理
set_defaults()
# 定数扱いするグローバル変数の初期値
ZEN2HAN = str.maketrans('０１２３４５６７８９'
                        + 'ａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺ'
                        + r'！＂＃＄％＆＇（）＊＋，－．／：；＜＝＞？＠［＼］＾＿｀｛｜｝～　',
                        '0123456789'
                        + 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'
                        + r'!"#$%&' + r"'()*+,-./:;<=>?@[⧵]^_`{|}~ ")
PATH = get_config('database.path')
if not os.path.isdir(PATH):
    raise notmuchVimError('\'' + PATH + '\' don\'t exist.')
if not notmuch_new(True):
    raise notmuchVimError('Can\'t update database.')
    vim.command('redraw')  # notmuch new の結果をクリア←redraw しないとメッセージが表示されるので、続けるためにリターンが必要
if 'notmuch_delete_top_subject' in vim.vars:  # Subject の先頭から削除する正規表現文字列
    DELETE_TOP_SUBJECT = vim.vars('notmuch_delete_top_subject').decode()
else:
    DELETE_TOP_SUBJECT = r'^\s*((R[Ee][: ]*\d*)?\[[A-Za-z -]+(:\d+)?\](\s*R[Ee][: ])?\s*' \
        + r'|(R[Ee][: ]*\d*)?\w+\.\d+:\d+\|( R[Ee][: ]\d+)? ?' \
        + r'|R[Ee][: ]+)*[　 ]*'
set_folder_format()
RE_TOP_SPACE = re.compile(r'^\s+')  # 先頭空白削除
RE_END_SPACE = re.compile(r'\s*$')  # 行末空白削除
RE_TAB2SPACE = re.compile('[　\t]+')  # タブと全角空白→スペース←スレッド・リストではできるだけ短く、タブはデリミタに使用予定
RE_DQUOTE = re.compile(r'\s*"([^"]+)"\s*')  # "に挟まれていれば挟まれている部分だけに
try:
    RE_SUBJECT = re.compile(DELETE_TOP_SUBJECT)
except re.error:
    print_warring('Error: Regurlar Expression.'
                  + '\nReset g:notmuch_delete_top_subject: ' + DELETE_TOP_SUBJECT
                  + '\nusing default settings.')
    DELETE_TOP_SUBJECT = r'^\s*((R[Ee][: ]*\d*)?\[[A-Za-z -]+(:\d+)?\](\s*R[Ee][: ])?\s*' \
        + r'|(R[Ee][: ]*\d*)?\w+\.\d+:\d+\|( R[Ee][: ]\d+)? ?' \
        + r'|R[Ee][: ]+)*[　 ]*'
    try:  # 先頭空白削除
        RE_SUBJECT = re.compile(DELETE_TOP_SUBJECT)
    except re.error:
        print_err('Error: Regurlar Expression')
THREAD_LISTS = {}
""" スレッド・リスト・データの辞書

    Example:
    THREAD_LISTS[search_term] = {'list': ls, 'sort': ['date']}
        search_term:   辞書のキーで検索キーワード
        list:          メール・データ
        sort:          ソート方法
"""
GLOBALS = globals()
# 一次処理に使うディレクトリの削除や異常終了して残っていたファイルを削除
make_dir(get_attach_dir())
make_dir(get_temp_dir())
rm_file(get_attach_dir())
rm_file(get_temp_dir())
