vim9script
# Author:  Iranoan <iranoan+vim@gmail.com>
# License: GPL Ver.3.

scriptencoding utf-8

# 下記の二重読み込み防止変数の前に取得しておかないと、途中の読み込み失敗時に設定されずに読み込むファイルの取得ができなくなる変数
var script_root: string = expand('<sfile>:p:h:h')
var buf_num: dict<any>

if !exists('g:loaded_notmuch_py')
	finish
endif
g:loaded_notmuch_py = 1

# Function
def Do_use_new_buffer(type: string): bool # 新規のバッファを開くか?
	# notmuch-folder の時だけバッファが空なら開き方に関係なく今のバッファをそのまま使う
	return !(
				   type ==# 'folders'
				&& wordcount().bytes == 0
				)
enddef

def New_buffer(type: string, search_term: string): void
	if Do_use_new_buffer(type)
		try
			execute substitute(g:notmuch_open_way[type], '\d\+', ':&', 'g')
		catch /^Vim\%((\a\+)\)\=:E36:/
			echomsg 'execute only command'
			win_gotoid(bufwinid(buf_num.folders))
			silent only
			execute substitute(g:notmuch_open_way[type], '\d\+', ':&', 'g')
		endtry
	endif
	if type !=? 'search' && type !=? 'view'
		buf_num[type] = bufnr('')
		b:notmuch = {}
	else
		buf_num[type][search_term] = bufnr('')
		b:notmuch = {}
	endif
	# キーマップ
	# draft/edit 以外共通
	nnoremap <buffer><silent><F1> :topleft help notmuch-python-vim-keymap<CR>
	nnoremap <buffer><silent><leader>h :topleft help notmuch-python-vim-keymap<CR>
	nnoremap <buffer><silent><Leader>s :Notmuch mail-send<CR>
	nnoremap <buffer><silent><Tab> <C-w>w
	nnoremap <buffer><silent><S-Tab> <C-w>W
	nnoremap <buffer><silent><space> :Notmuch view-unread-page<CR>
	nnoremap <buffer><silent><BS> :Notmuch view-previous<CR>
	nnoremap <buffer><silent>J :Notmuch view-unread-mail<CR>
	nnoremap <buffer><silent><C-R> :Notmuch reload<CR>
	nnoremap <buffer><silent>p :Notmuch mail-info<CR>
	nnoremap <buffer><silent>I :Notmuch mail-export<CR>
	nnoremap <buffer><silent>R :Notmuch mail-forward<CR>
	nnoremap <buffer><silent>c :Notmuch mail-new<CR>
	nnoremap <buffer><silent>i :Notmuch mail-import<CR>
	nnoremap <buffer><silent>r :Notmuch mail-reply<CR>
	if type ==# 'folders'
		setlocal filetype=notmuch-folders
	elseif type ==# 'thread' || type ==# 'search'
		setlocal filetype=notmuch-thread
	elseif type ==# 'show' || type ==# 'view'
		setlocal filetype=notmuch-show
	endif
	setlocal modifiable buftype=nofile bufhidden=hide noequalalways fileencoding=utf-8 noswapfile
	keepjumps :0d
enddef

def Change_exist_tabpage(type: string, search_term: string): void
	var l_buf_num: number
	if type !=? 'search' && type !=? 'view'
		l_buf_num = buf_num[type]
	else
		l_buf_num = buf_num[type][search_term]
	endif
	Change_exist_tabpage_core(l_buf_num)
enddef

def Change_exist_tabpage_core(bufnum: number): void
	var tabpage: number = 0
	for i in range(tabpagenr('$'))
		if index(tabpagebuflist(i + 1), bufnum) != -1
			tabpage = i + 1
			break
		endif
	endfor
	if tabpage != 0 # タブページが有る場合
		execute ':' .. tabpage .. 'tabnext'
	endif
enddef

def Make_folders_list(): void
	if has_key(buf_num, 'folders') # && bufname(buf_num.folders) !=? ''
		Change_exist_tabpage_core(buf_num.folders)
		if bufwinid(buf_num.folders) == -1
			py3 reopen('folders', '')
		else
			win_gotoid(bufwinid(buf_num.folders))
		endif
		Close_notmuch('thread')
		Close_notmuch('show')
		Close_notmuch('search')
		Close_notmuch('view')
		var open_way: string = g:notmuch_open_way.folders
		if open_way ==# 'enew' || open_way ==# 'tabedit'
			silent only
		endif
	else
		New_buffer('folders', '')
		execute('silent file! notmuch://folder?' .. getcwd())
		py3 print_folder()
		augroup NotmuchMakeFolder
			autocmd!
			autocmd BufWipeout <buffer> End_notmuch()
		augroup END
	endif
enddef

def Make_thread_list(): void # スレッド・バッファを用意するだけ
	if has_key(buf_num, 'thread') # && bufname(buf_num.thread) !=? ''
		py3 reopen('thread', '')
		return
	endif
	New_buffer('thread', '')
	Set_thread(buf_num.thread)
	silent file! notmuch://thread
	augroup NotmuchMakeThread
		autocmd!
		autocmd BufWipeout <buffer> unlet buf_num.thread
	augroup END
	if g:notmuch_open_way.show !=? 'enew' && g:notmuch_open_way.show !=? 'tabedit'
		Make_show()
	endif
enddef

def Make_search_list(search_term: string): void
	if has_key(buf_num.search, search_term)
		py3eval('reopen("search", "' .. escape(search_term, '"') .. '")')
		return
	endif
	New_buffer('search', search_term)
	var l_bufnr = bufnr()
	Set_thread(l_bufnr)
	execute 'augroup NotmuchMakeSearch' .. l_bufnr
		autocmd!
		execute 'autocmd BufWipeout <buffer=' .. l_bufnr .. '> unlet buf_num.search[b:notmuch.search_term]' ..
					'| autocmd! NotmuchMakeSearch' .. l_bufnr ..
					'| augroup! NotmuchMakeSearch' .. l_bufnr ..
					'| autocmd! NotmuchSetThread' .. l_bufnr ..
					'| augroup! NotmuchSetThread' .. l_bufnr
	augroup END
	if g:notmuch_open_way.view !=? 'enew' && g:notmuch_open_way.view !=? 'tabedit'
		Make_view(search_term)
	endif
enddef

def Set_thread(n: number): void
	b:notmuch.tags = ''
	b:notmuch.search_term = ''
	b:notmuch.msg_id = ''
	execute 'augroup NotmuchSetThread' .. n
		autocmd!
		execute 'autocmd CursorMoved <buffer=' .. n .. '> Cursor_move_thread(b:notmuch.search_term)'
	augroup END
enddef

function Open_something(args) abort
	py3 open_something(vim.eval('a:args'))
endfunction

def Next_thread(args: list<any>): void
	var type = py3eval('buf_kind()')
	if type == 'thread' || type == 'search'
		normal! j
		py3 fold_open()
	endif
enddef

def Make_show(): void # メール・バッファを用意するだけ
	if has_key(buf_num, 'show') # && bufname(buf_num.show) !=? ''
		py3 reopen('show', '')
		return
	endif
	New_buffer('show', '')
	Set_show()
	silent file! notmuch://show
	augroup NotmuchMakeShow
		autocmd!
		autocmd BufWipeout <buffer> unlet buf_num.show
	augroup END
enddef

def Make_view(search_term: string): void # メール・バッファを用意するだけ
	if has_key(buf_num.view, search_term)
		py3eval('reopen("view", "' .. escape(search_term, '"') .. '")')
		return
	endif
	New_buffer('view', search_term)
	var l_bufnr = bufnr()
	Set_show()
	execute 'augroup NotmuchMakeView' .. l_bufnr
		autocmd!
		execute 'autocmd BufWipeout <buffer=' .. l_bufnr .. '> unlet buf_num.view[b:notmuch.search_term]' ..
					'| autocmd! NotmuchMakeView' .. l_bufnr ..
					'| augroup! NotmuchMakeView' .. l_bufnr
	augroup END
enddef

def Set_show(): void
	b:notmuch.msg_id = ''
	b:notmuch.subject = ''
	b:notmuch.date = ''
	b:notmuch.tags = ''
enddef

def Next_unread_page(args: list<any>): void # メール最後の行が表示されていればスクロールしない+既読にする
	var l_buf_num = bufnr('')
	if !has_key(buf_num, 'thread')
		Make_thread_list()
	endif
	if !has_key(buf_num, 'show')
		Make_show()
	endif
	if win_gotoid(bufwinid(buf_num.show)) == 0
		if has_key(buf_num, 'view')
					&& has_key(b:notmuch, 'search_term')
					&& b:notmuch.search_term !=# ''
					&& has_key(buf_num.view, b:notmuch.search_term)
			win_gotoid(bufwinid(buf_num.view[b:notmuch.search_term]))
		else
			py3 reopen('show', '')
		endif
	endif
	if !exists('b:notmuch.msg_id') || b:notmuch.msg_id ==# ''
		py3eval('next_unread(' .. l_buf_num .. ')')
		return
	endif
	if line('w$') == line('$') # 最終行表示
		var column = col('.')
		if line('w0') == line('w$') # 最終行表示でも 表示先頭行=表示最終行 なら折り返し部分が非表示の可能性→カーソル移動
			execute 'normal!' 2 * winheight(0) - winline() - 1 .. 'gj'
			if column == col('.')
				py3 delete_tags(vim.current.buffer.vars['notmuch']['msg_id'].decode(), '', [0, 0, 'unread'])
				py3eval('next_unread(' .. l_buf_num .. ')')
			endif
		else
			py3 delete_tags(vim.current.buffer.vars['notmuch']['msg_id'].decode(), '', [0, 0, 'unread'])
			py3eval('next_unread(' .. l_buf_num .. ')')
		endif
	elseif line('w0') != line('w$') # 一行で 1 ページ全体ではない
		execute 'normal!' winheight(0) - winline() + 1 .. 'gjzt' # 表示している最終行が折り返し行だと <PageDown> ではうまくいかない
		if line('w$') == line('$') # 表示最終行 = 最終行 なら最後まで表示
			py3 delete_tags(vim.current.buffer.vars['notmuch']['msg_id'].decode(), '', [0, 0, 'unread'])
		endif
	else # 一行で 1 ページ全体
		var pos = line('.')
		execute 'normal!' winheight(0) - winline() + 1 .. 'gj'
		if line('.') != pos # 移動前に表示していた次の行までカーソル移動して、行番号が異なれば行の最後まで表示されていた
			cursor(pos, 0) # 一旦前の位置に移動し次で次行を画面最上部に表示
			normal! jzt
		else # 行の途中まで表示していた
			execute 'normal!' winheight(0) - 2 .. 'gj'
			# ↑追加で 1 ページ分カーソル移動←本当はページ先頭に戻したいがやり方がわからない
			if line('.') != pos # カーソル移動して行番号異なれば、以降の行まで移動した
				cursor(pos, 0) # 一旦前の位置に移動し次で行末の表示先頭桁に移動
				normal! $g^
			endif
		endif
	endif
	win_gotoid(bufwinid(l_buf_num))
enddef

def Next_unread(args: list<any>): void
	py3eval('next_unread(' .. bufnr('') .. ')')
enddef

def Previous_page(args: list<any>): void
	var l_buf_num = bufnr('')
	if !has_key(buf_num, 'thread')
		Make_thread_list()
	endif
	if !has_key(buf_num, 'show')
		Make_show()
	endif
	if win_gotoid(bufwinid(buf_num.show)) == 0
		if has_key(buf_num, 'view')
					&& has_key(b:notmuch, 'search_term')
					&& b:notmuch.search_term !=# ''
					&& has_key(buf_num.view, b:notmuch.search_term)
			win_gotoid(bufwinid(buf_num.view[b:notmuch.search_term]))
		else
			py3 reopen('show', '')
		endif
	endif
	execute "normal! \<PageUp>"
	win_gotoid(bufwinid(l_buf_num))
enddef

function Save_attachment(args) abort
	py3 save_attachment(vim.eval('a:args'))
endfunction

def View_mail_info(args: list<any>): void
	py3 view_mail_info()
enddef

export def Close_popup(id: number, key: string): bool
	if key ==? 'x' || key ==? 'q' || key ==? 'c' || key ==? 'o' || key ==? 'p' || key ==? "\<Esc>"
		popup_close(id)
		return 1
	else
		return 0
	endif
enddef

function Delete_tags(args) abort
	py3 do_mail(delete_tags, vim.eval('a:args'))
endfunction

def Complete_tag_common(func: string, cmdLine: string, cursorPos: number, direct_command: bool): list<string>
	var tags: list<string> = Get_snippet(func, cmdLine, cursorPos, direct_command)
	var filter: string
	for t in split(cmdLine)[2 : ]
		filter = printf('v:val !~? "^%s\\>"', t)
		tags = filter(tags, filter)
	endfor
	if len(tags) != 1
		return tags
	endif
	return [ tags[0] .. ' ' ]
enddef

def Get_snippet(func: string, cmdLine: string, cursorPos: number, direct_command: bool): list<string>  # list から cmdLine カーソル位置の単語から補完候補を取得
	var l_cmdLine: list<string> = split(cmdLine[0 : cursorPos - 1], ' ')
	var prefix: string
	var filter: string
	if cmdLine[cursorPos - 1] ==# ' '
		filter = ''
		prefix = join(l_cmdLine, ' ')
	elseif cmdLine !=? ''
		filter = l_cmdLine[-1]
		prefix = join(l_cmdLine[0 : -2], ' ')
	else
		filter = ''
		prefix = ''
	endif
	if prefix !=?  ''
		prefix = prefix .. ' '
	endif
	var ls: list<string> = py3eval(func .. '("' .. escape(filter, '"') .. '")')
	filter = printf('v:val =~? "^%s"', filter)
	var snippet_org: list<string> = filter(ls, filter)
	if direct_command  # input() 関数ではなく、command 直接の補完
		return snippet_org
	endif
	# 補完候補にカーソル前の文字列を追加
	var snippet: list<string>
	for v in snippet_org
		add(snippet, prefix .. v)
	endfor
	return snippet
enddef

def Get_sort_snippet(cmdLine: string, cursorPos: number, direct_command: bool): list<string>
	var l_cmdLine: list<string> = split(cmdLine[0 : cursorPos - 1], ' ')
	var filter: string
	var prefix: string
	if cmdLine[cursorPos - 1] ==# ' '
		filter = ''
		prefix = join(l_cmdLine, ' ')
	elseif cmdLine !=? ''
		filter = l_cmdLine[-1]
		prefix = join(l_cmdLine[0 : -2], ' ')
	else
		filter = ''
		prefix = ''
	endif
	if prefix !=?  ''
		prefix = prefix .. ' '
	endif
	var ls: list<string> = ['list', 'tree', 'Date', 'date', 'From', 'from', 'Subject', 'subject']
	filter = printf('v:val =~# "^%s"', filter)
	var snippet_org: list<string>  = filter(ls, filter)
	if direct_command  # input() 関数ではなく、command 直接の補完
		return snippet_org
	endif
	# 補完候補にカーソル前の文字列を追加
	var snippet: list<string>
	for v in snippet_org
		add(snippet, prefix .. v)
	endfor
	return snippet
enddef

export def Comp_sort(ArgLead: string, CmdLine: string, CursorPos: number): list<any>
	var snippet: list<any> = Get_sort_snippet(CmdLine, CursorPos, false)
	return Is_one_snippet(snippet)
enddef

export def Comp_del_tag(ArgLead: string, CmdLine: string, CursorPos: number): list<any>
	return Complete_tag_common('get_msg_tags_list', CmdLine, CursorPos, false)
enddef

function Add_tags(args) abort
	py3 do_mail(add_tags, vim.eval('a:args'))
endfunction

export def Comp_add_tag(ArgLead: string, CmdLine: string, CursorPos: number): list<any>
	return Complete_tag_common('get_msg_tags_diff', CmdLine, CursorPos, false)
enddef

function Set_tags(args) abort
	py3 do_mail(set_tags, vim.eval('a:args'))
endfunction

export def Comp_set_tag(ArgLead: string, CmdLine: string, CursorPos: number): list<any>
	return Complete_tag_common('get_msg_tags_any_kind', CmdLine, CursorPos, false)
enddef

function Toggle_tags(args) abort
	py3 do_mail(toggle_tags, vim.eval('a:args'))
endfunction

export def Comp_tag(ArgLead: string, CmdLine: string, CursorPos: number): list<any>
	return Complete_tag_common('get_msg_all_tags_list', CmdLine, CursorPos, false)
enddef

export def Notmuch_main(...arg: list<any>): void
	if len(arg) == 2
		help notmuch-python-vim-command
		echohl WarningMsg | echomsg 'Requires argument (subcommand).' | echomsg 'open help.' | echohl None
	else
		var cmd: list<any> = copy(arg)
		var sub_cmd: string = remove(cmd, 2)
		if !has_key(g:notmuch_command, sub_cmd)
			help notmuch-python-vim-command
			echohl WarningMsg | echomsg 'Not exist ' .. sub_cmd .. ' subcommand.' | echomsg 'open help.' | echohl None
		else
			if sub_cmd ==# 'start'
				Start_notmuch()
			elseif sub_cmd ==# 'mail-new'
				remove(cmd, 0, 1)
				New_mail(join(cmd, ' '))
			else
				function(g:notmuch_command[sub_cmd][0])(cmd)
			endif
		endif
	endif
enddef

def Import(): void
	python3 << _EOF_
import os, sys, vim
if 'notmuchVim' not in sys.modules:
    if not vim.eval('script_root') + '/autoload/' in sys.path:
        sys.path.append(vim.eval('script_root') + '/autoload/')
    import notmuchVim
    # vim から呼び出す関数は関数名だけで呼び出せるようにする
    from notmuchVim.subcommand import add_tags
    from notmuchVim.subcommand import buf_kind
    from notmuchVim.subcommand import command_marked
    from notmuchVim.subcommand import connect_thread_tree
    from notmuchVim.subcommand import cursor_move_thread
    from notmuchVim.subcommand import cut_thread
    from notmuchVim.subcommand import delete_attachment
    from notmuchVim.subcommand import delete_mail
    from notmuchVim.subcommand import delete_tags
    from notmuchVim.subcommand import do_mail
    from notmuchVim.subcommand import export_mail
    from notmuchVim.subcommand import fold_open
    from notmuchVim.subcommand import forward_mail
    from notmuchVim.subcommand import forward_mail_attach
    from notmuchVim.subcommand import forward_mail_resent
    from notmuchVim.subcommand import get_cmd_name
    from notmuchVim.subcommand import get_cmd_name_ftype
    from notmuchVim.subcommand import get_command
    from notmuchVim.subcommand import get_folded_list
    from notmuchVim.subcommand import get_hide_header
    from notmuchVim.subcommand import get_last_cmd
    from notmuchVim.subcommand import get_mail_folders
    from notmuchVim.subcommand import get_mark_cmd_name
    from notmuchVim.subcommand import get_msg_all_tags_list
    from notmuchVim.subcommand import get_msg_id
    from notmuchVim.subcommand import get_msg_tags_any_kind
    from notmuchVim.subcommand import get_msg_tags_diff
    from notmuchVim.subcommand import get_msg_tags_list
    from notmuchVim.subcommand import get_save_dir
    from notmuchVim.subcommand import get_save_filename
    from notmuchVim.subcommand import get_search_snippet
    from notmuchVim.subcommand import get_sys_command
    from notmuchVim.subcommand import import_mail
    from notmuchVim.subcommand import is_same_tabpage
    from notmuchVim.subcommand import make_dump
    from notmuchVim.subcommand import move_mail
    from notmuchVim.subcommand import new_mail
    from notmuchVim.subcommand import next_unread
    from notmuchVim.subcommand import notmuch_address
    from notmuchVim.subcommand import notmuch_down_refine
    from notmuchVim.subcommand import notmuch_duplication
    from notmuchVim.subcommand import notmuch_refine
    from notmuchVim.subcommand import notmuch_search
    from notmuchVim.subcommand import notmuch_thread
    from notmuchVim.subcommand import notmuch_up_refine
    from notmuchVim.subcommand import open_original
    from notmuchVim.subcommand import open_something
    from notmuchVim.subcommand import print_folder
    from notmuchVim.subcommand import reindex_mail
    from notmuchVim.subcommand import reload
    from notmuchVim.subcommand import reopen
    from notmuchVim.subcommand import reply_mail
    from notmuchVim.subcommand import reset_cursor_position
    from notmuchVim.subcommand import run_shell_program
    from notmuchVim.subcommand import save_attachment
    from notmuchVim.subcommand import save_mail
    from notmuchVim.subcommand import save_draft
    from notmuchVim.subcommand import send_vim
    from notmuchVim.subcommand import set_attach
    from notmuchVim.subcommand import set_encrypt
    from notmuchVim.subcommand import set_fcc
    from notmuchVim.subcommand import set_forward_after
    from notmuchVim.subcommand import set_new_after
    from notmuchVim.subcommand import set_reply_after
    from notmuchVim.subcommand import set_resent_after
    from notmuchVim.subcommand import set_subcmd_newmail
    from notmuchVim.subcommand import set_subcmd_start
    from notmuchVim.subcommand import set_tags
    from notmuchVim.subcommand import thread_change_sort
    from notmuchVim.subcommand import toggle_tags
    from notmuchVim.subcommand import view_mail_info
_EOF_
enddef

def Start_notmuch(): void
	if !exists('buf_num')
		buf_num = {}
	endif
	if !has_key(buf_num, 'search')
		buf_num.search = {}
	endif
	if !has_key(buf_num, 'view')
		buf_num.view = {}
	endif
	Import()
	py3 set_subcmd_start()
	execute 'cd ' .. py3eval('get_save_dir()')
	Make_folders_list()
	Set_title_etc()
	if g:notmuch_open_way.thread !=? 'enew' && g:notmuch_open_way.thread !=? 'tabedit'
		Make_thread_list()
		win_gotoid(bufwinid(buf_num.folders))
	endif
	# guifg=red ctermfg=red
	# 次の変数は Python スクリプトを読み込んでしまえばもう不要←一度閉じて再び開くかもしれない
	# unlet script_root
enddef

def Close_notmuch(kind: string): void
	if !has_key(buf_num, kind)
		return
	endif
	var bufs: list<number>
	if kind ==# 'thread' || kind ==# 'show'
		bufs = [buf_num[kind]]
	else
		bufs = values(buf_num[kind])
	endif
	for b in bufs
		Change_exist_tabpage_core(b)
		if win_gotoid(bufwinid(b))
			close
		endif
	endfor
enddef

def Vim_escape(s: string): string # Python に受け渡す時に \, ダブルクォートをエスケープ
	return substitute(substitute(s, '\\', '\\\\', 'g'), '''', '\\\''', 'g')
enddef

export def GetGUITabline(): string
	def Get_gui_tab(notmuch_dic: dict<any>): string
		if has_key(notmuch_dic, 'search_term')
			return 'notmuch [' .. notmuch_dic.search_term .. ']%<'
		else # notmuch-search 作成直後は b:notmuch.search_term 未定義
			return 'notmuch []%<'
		endif
	enddef

	var type = py3eval('buf_kind()')
	var vars = getbufinfo(bufnr())[0].variables
	if type ==# 'edit'
		return '%{b:notmuch.subject}%<%{b:notmuch.date}'
	elseif type ==# 'show'
		if py3eval('is_same_tabpage("thread", "")')
			return Get_gui_tab(getbufinfo(buf_num.thread)[0].variables.notmuch)
		else
			return '%{b:notmuch.subject}%<%{b:notmuch.date}'
		endif
	elseif type ==# 'view' && has_key(vars.notmuch, 'search_term')
		if py3eval('is_same_tabpage("search", ''' .. Vim_escape(b:notmuch.search_term) .. ''')')
			return 'notmuch [' .. b:notmuch.search_term .. ']%<'
		else
			return '%{b:notmuch.subject}%<%{b:notmuch.date}'
		endif
	elseif type ==# 'draft'
		return 'notmuch [Draft] %{b:notmuch.subject}%<'
	elseif type ==# 'search'
		return Get_gui_tab(vars.notmuch)
	elseif has_key(buf_num, 'thread') # notmuch-folder では notmuch-search と同じにするのを兼ねている
		return Get_gui_tab(getbufinfo(buf_num.thread)[0].variables.notmuch)
	else
		return Get_gui_tab(vars.notmuch)
	endif
enddef

def Set_title_etc(): void
	if &title && &titlestring ==# ''
		augroup NotmuchTitle
			autocmd!
			autocmd BufEnter,BufFilePost * &titlestring = Make_title()
		augroup END
	endif
	if has('gui_running') && &showtabline != 0 && &guitablabel ==# ''
		set guitablabel=%{%&filetype!~#'^notmuch-'?'%t':notmuch_py#GetGUITabline()%}
	endif
enddef

def Make_title(): string
	var tablist: number = tabpagenr('$')
	var a: string
	var title: string
	if tablist == 1
		a = ''
	else
		a = ' (' .. tabpagenr() .. ' of ' .. tablist .. ')'
	endif
	if &filetype =~# '^notmuch-'
		title = 'Notmuch-Python-Vim'
	elseif &filetype ==# 'qf'
		title = '%t'
	elseif &filetype ==# 'help'
		title = '%h'
	elseif bufname('') ==# ''
		title = '%t %m'
	else
		title = '%t %m ' .. '(' .. expand('%:~:h') .. ')'
	endif
	return title .. a .. ' - ' .. v:servername
enddef

def Search_not_notmuch(): number # notmuch-? 以外のリストされていて隠れていない、もしくは隠れていても更新されているバッファを探す
	var notmuch_kind: list<string> = ['notmuch-folders', 'notmuch-thread', 'notmuch-show', 'notmuch-edit', 'notmuch-draft']
	var changed: number = 0
	for buf in getbufinfo()
		if count(notmuch_kind, getbufvar(buf.bufnr, '&filetype')) == 0
			if !buf.listed
				continue
			elseif buf.hidden
				if buf.changed
					changed = buf.bufnr
				endif
			else
				return buf.bufnr
			endif
		endif
	endfor
	if changed != 0
		return changed
	endif
	return 0
enddef

def End_notmuch(): void # 全て終了 (notmuch-folders が bwipeout されたら呼ばれる)
	var bufinfo: list<dict<any>> = getbufinfo()
	var bufnr: number
	var ftype: string
	for buf in bufinfo
		bufnr = buf.bufnr
		ftype = getbufvar(bufnr, '&filetype')
		if ftype ==# 'notmuch-draft' && buf.changed || ( ftype ==# 'notmuch-edit' && buf.changed )
			Swich_buffer(bufnr)
			echohl WarningMsg | echo 'Editing ' .. ftype .. '.' | echohl None
			unlet buf_num.folders
			return
		endif
	endfor
	py3 make_dump()
	bufnr = Search_not_notmuch()
	if bufnr == 0
		cquit # →全終了
	endif
	Swich_buffer(bufnr)
	# notmuch-* バッファ削除
	var notmuch_kind: list<string> = ['notmuch-folder', 'notmuch-thread', 'notmuch-show', 'notmuch-edit', 'notmuch-draft']
	for buf in bufinfo
		bufnr = buf.bufnr
		if count(notmuch_kind, getbufvar(bufnr, '&filetype'))
			execute ':' .. bufnr .. 'bwipeout'
		endif
	endfor
	Change_fold_highlight()
	buf_num = {}
	s_select_thread = -1
enddef

def Swich_buffer(bufnr: number): void # できるだけ指定されたバッファに切り替える
	# 他のタブページに有るか?
	var tabpage: number = 0
	for i in range(tabpagenr('$'))
		if match(tabpagebuflist(i + 1), '' .. bufnr) != -1
			tabpage = i + 1
			break
		endif
	endfor
	if tabpage != 0 # タブページが有る場合
		execute ':' .. tabpage .. 'tabnext'
	endif
	if win_gotoid(bufwinid(bufnr)) == 0
		var type: string = getbufvar(bufnr, '&filetype')
		if type ==# 'notmuch-edit' || type ==# 'notmuch-draft'
			var open_way: string = g:notmuch_open_way[strpart(type, 8)]
			if open_way ==# 'enew'
				execute 'silent buffer ' .. bufnr
			elseif open_way ==# 'tabedit'
				execute 'silent tab sbuffer ' .. bufnr
			else
				open_way = substitute(open_way, '\<new\>',           'split',     '')
				open_way = substitute(open_way, '\([0-9]\+\)new\>',  ':\1split',  '')
				open_way = substitute(open_way, '\<vnew\>',          'vsplit',    '')
				open_way = substitute(open_way, '\([0-9]\+\)vnew\>', ':\1vsplit', '')
				execute open_way
				execute 'silent buffer ' .. bufnr
			endif
		else
			execute ':' .. bufnr .. 'buffer'
		endif
	endif
enddef

function Open_original(args) abort
	py3 do_mail(open_original, vim.eval('a:args'))
endfunction

def Reload(args: list<any>): void
	py3 reload()
enddef

def Cursor_move_thread(search_term: string): void
	if line('.') != line('v')
		return
	endif
	py3eval('cursor_move_thread("' .. escape(search_term, '"') .. '")')
enddef

function New_mail(...) abort
	if !py3eval('"DBASE" in globals()')  " フォルダ一覧も非表示状態で呼ばれた場合
		call s:Import()
		py3 set_subcmd_newmail()
		execute 'cd ' .. py3eval('get_save_dir()')
		if &title && &titlestring ==# ''
			let &titlestring=s:Make_title()
		endif
		if has('gui_running') && &showtabline != 0 && &guitablabel ==# ''
			set guitablabel=%{%&filetype!~#'^notmuch-'?'%t':notmuch_py#GetGUITabline()%}
		endif
	endif
	py3 new_mail(vim.eval('a:000'))
endfunction

def Forward_mail(args: list<any>): void
	py3 forward_mail()
enddef

def Forward_mail_attach(args: list<any>): void
	py3 forward_mail_attach()
enddef

def Forward_mail_resent(args: list<any>): void
	py3 forward_mail_resent()
enddef

def Reply_mail(args: list<any>): void
	py3 reply_mail()
enddef

def Send_vim(args: list<any>): void
	py3 send_vim()
enddef

function Save_mail(args) abort
	if len(a:args) > 3
		py3 do_mail(save_mail, vim.eval('a:args[:2]'))
	else
		py3 do_mail(save_mail, vim.eval('a:args'))
	endif
endfunction

function Move_mail(args) abort
	py3 do_mail(move_mail, vim.eval('a:args'))
endfunction

export def Comp_dir(ArgLead: string, CmdLine: string, CursorPos: number): list<any>
	var folders: list<any> = py3eval('get_mail_folders()')
	return filter(folders, printf('v:val =~? "^%s"', ArgLead))
enddef

function Run_shell_program(args) abort
	py3 do_mail(run_shell_program, vim.eval('a:args'))
endfunction

function Reindex_mail(args) abort
	py3 do_mail(reindex_mail, vim.eval('a:args'))
endfunction

function Import_mail(args) abort
	py3 import_mail(vim.eval('a:args'))
endfunction

function Delete_mail(args) abort
	py3 do_mail(delete_mail, vim.eval('a:args'))
endfunction

function Export_mail(args) abort
	py3 do_mail(export_mail, vim.eval('a:args'))
endfunction

function Delete_attachment(args) abort
	py3 delete_attachment(vim.eval('a:args'))
endfunction

def CloseCore(): void # notmuch-* を閉じる (閉じるメイン部分)
	if winnr('$') == 1 && tabpagenr('$') == 1
		var bufnr: number = Search_not_notmuch()
		if bufnr
			execute ':' .. bufnr .. 'buffer'
		else
			quit
		endif
	else
		close
	endif
enddef

def Close(args: list<any>): void # notmuch-* を閉じる (基本 close なので隠すだけ) が、他のバッファが残っていれば Vim を終了させずに、そのバッファを復活させる
	CloseCore()
enddef

def CloseTab(args: list<any>): void # notmuch-* を閉じる
	# タブ・ページに notmuch-folder があれば、notmuch-* すべての終了を試みる
	# そうでない場合、互いに対応する notmuch-thread/notmuch-show を閉じる
	var bufnum: number = bufnr('')

	def ClosePareCore(pair_b: number)
		var c_tab: number = tabpagenr()
		for b in tabpagebuflist()
			if b == bufnum || b == pair_b
				for w in getbufinfo(b)[0].windows
					if c_tab == win_id2tabwin(w)[0]
						win_gotoid(w)
						CloseCore()
					endif
				endfor
			endif
		endfor
	enddef

	def ClosePare(buf_dic: dict<any>, s: string)
		if !has_key(buf_dic, s)
			CloseCore()
			return
		endif
		ClosePareCore(buf_dic[s])
	enddef

	def ClosePareSearch(buf_dic: dict<any>, k: string): void
		var s: string = getbufinfo('')[0].variables.notmuch.search_term
		if !has_key(buf_dic, k)
			CloseCore()
			return
		elseif !has_key(buf_dic[k], s)
			CloseCore()
			return
		endif
		ClosePareCore(buf_dic[k][s])
	enddef

	for b in tabpagebuflist()
		if b == buf_num.folders
			execute 'bwipeout ' .. b
			return
		endif
	endfor
	if &filetype ==# 'notmuch-edit' || &filetype ==# 'notmuch-draft'
		close
	elseif buf_num['thread'] == bufnum
		ClosePare(buf_num, 'show')
	elseif buf_num['show'] == bufnum
		ClosePare(buf_num, 'thread')
	elseif &filetype ==# 'notmuch-thread'
		ClosePareSearch(buf_num, 'view')
	elseif &filetype ==#  'notmuch-show'
		ClosePareSearch(buf_num, 'search')
	endif
enddef

def Au_edit(win: number, search_term: string, reload: bool): void # 閉じた時の処理 (呼び出し元に戻り reload == true で notmuch-show, notmuch-view が同じタブページに有れば再読込)
	var l_bufnr = bufnr()
	execute 'augroup NotmuchEdit' .. l_bufnr
		autocmd!
		execute 'autocmd BufWinLeave <buffer> Change_exist_tabpage_core(' .. win .. ') |' ..
					(reload ?
						(search_term ==# '' ?  'if py3eval(''is_same_tabpage("show", "")'') |'
						: 'if py3eval(''is_same_tabpage("view", "' .. escape(search_term, '"') .. '")'') |') ..
								'win_gotoid(bufwinid(buf_num["show"])) | ' ..
								'Reload([]) |' ..
							'endif | '
					: '') ..
							'win_gotoid(bufwinid(' .. win .. ')) |' ..
							'autocmd! NotmuchEdit' .. l_bufnr .. ' |' ..
							'augroup! NotmuchEdit' .. l_bufnr
	augroup END
enddef

def Au_new_mail(): void # 新規/添付転送メールでファイル末尾移動時に From 設定や署名の挿入
	var l_bufnr = bufnr()
	execute 'augroup NotmuchNewAfter' .. l_bufnr
		autocmd!
		execute 'autocmd CursorMoved,CursorMovedI <buffer=' .. l_bufnr .. '> py3eval("set_new_after(' .. l_bufnr .. ')")'
	augroup END
enddef

def Au_reply_mail(): void # 返信メールでファイル末尾移動時に From 設定や署名・返信元引用文の挿入
	var l_bufnr = bufnr()
	execute 'augroup NotmuchReplyAfter' .. l_bufnr
		autocmd!
		execute 'autocmd CursorMoved,CursorMovedI <buffer=' .. l_bufnr .. '> py3eval("set_reply_after(' .. l_bufnr .. ')")'
	augroup END
enddef

def Au_forward_mail(): void # 転送メールでファイル末尾移動時に From 設定や署名・転送元の挿入
	var l_bufnr = bufnr()
	execute 'augroup NotmuchForwardAfter' .. l_bufnr
		autocmd!
		execute 'autocmd CursorMoved,CursorMovedI <buffer=' .. l_bufnr .. '> py3eval("set_forward_after(' .. l_bufnr .. ')")'
	augroup END
enddef

def Au_resent_mail(): void # 転送メールでファイル末尾移動時に From 設定や署名・転送元の挿入
	var l_bufnr = bufnr()
	execute 'augroup NotmuchResentAfter' .. l_bufnr
		autocmd!
		execute 'autocmd CursorMoved,CursorMovedI <buffer=' .. l_bufnr .. '> py3eval("set_resent_after(' .. l_bufnr .. ')")'
	augroup END
enddef

def Au_write_draft(): void # draft mail の保存
	var l_bufnr = bufnr()
	execute 'augroup NotmuchSaveDraft' .. l_bufnr
		autocmd!
		autocmd BufWrite <buffer> py3 save_draft()
		execute 'autocmd BufWipeout <buffer=' .. l_bufnr .. '> autocmd! NotmuchSaveDraft' .. l_bufnr
	augroup END
enddef

function Mark_in_thread(args) range abort
	let l:beg = a:args[0]
	let l:end = a:args[1]
	let l:bufnr = bufnr('')
	if !( l:bufnr == s:buf_num.thread
				\ || ( py3eval('buf_kind()') ==# 'search' && l:bufnr != s:buf_num.search[b:notmuch.search_term] )
				\ || py3eval('get_msg_id()') !=? '' )
				return
	endif
	if sign_getplaced('', {'name':'notmuch', 'group':'mark_thread', 'lnum':line('.') })[0].signs == []
		for l:i in range(l:beg, l:end)
			if sign_getplaced('', {'name':'notmuch', 'group':'mark_thread', 'lnum':l:i })[0].signs == []
				call sign_place(0, 'mark_thread', 'notmuch', '',{'lnum':l:i})
			endif
		endfor
	else
		for l:i in range(l:beg, l:end)
			let l:id = sign_getplaced('', {'name':'notmuch', 'group':'mark_thread', 'lnum':l:i })[0].signs
			if l:id != []
				call sign_unplace('mark_thread', {'name':'notmuch', 'buffer':'', 'id':l:id[0].id })
			endif
		endfor
	endif
	if l:beg == l:end
		py3 fold_open()
		normal! j
		py3 fold_open()
	endif
endfunction

def Cut_thread(args: list<any>): void
	py3 cut_thread(get_msg_id(), [])
enddef

def Connect_thread(args: list<any>): void
	py3 connect_thread_tree()
enddef

function Command_marked(args) abort " マークしたメールに纏めてコマンド実行
	call remove(a:args, 0, 1)
	py3 command_marked(vim.eval('a:args'))
endfunction

export def Comp_all_args(ArgLead: string, CmdLine: string, CursorPos: number): list<any>
	var cmdline: string = substitute(CmdLine, '[\n\r]\+', ' ', 'g')
	var last: list<any> = py3eval('get_last_cmd(get_cmd_name(), "' .. cmdline .. '", ' .. CursorPos .. ')')
	var snippet: list<string>
	if last == []
		snippet = py3eval('get_cmd_name_ftype()')
	else
		var cmd: string = last[0]
		# cmds = py3eval('get_command()')
		if and(g:notmuch_command[cmd][1], 0x01) == 0
			return []
		else
			if match(CmdLine, 'Notmuch \+mark-command *') != -1
				var index: number = matchend(CmdLine, '\m\CNotmuch \+mark-command *')
				return Complete_command(strpart(CmdLine, index), CursorPos - index, true)
			elseif cmd ==# 'run'
				snippet = py3eval('get_sys_command(''' .. Vim_escape(CmdLine) .. ''' , ''' .. Vim_escape(ArgLead) .. ''')')
			elseif cmd ==# 'mail-move' || cmd ==# 'set-fcc'
				if last[1] # 既にサブ・コマンドの引数が有る
					return []
				endif
				snippet = py3eval('get_mail_folders()')
			elseif cmd ==# 'tag-add'
				return Complete_tag_common('get_msg_tags_diff', CmdLine, CursorPos, true)
			elseif cmd ==# 'tag-delete'
				return Complete_tag_common('get_msg_tags_list', CmdLine, CursorPos, true)
			elseif cmd ==# 'tag-set'
				return Complete_tag_common('get_msg_tags_any_kind', CmdLine, CursorPos, true)
			elseif cmd ==# 'tag-toggle'
				return Complete_tag_common('get_msg_all_tags_list', CmdLine, CursorPos, true)
			elseif cmd ==# 'search' || cmd ==# 'search-refine'
				snippet = Get_snippet('get_search_snippet', CmdLine, CursorPos, true)
				return Is_one_snippet(snippet)
			elseif cmd ==# 'thread-sort'
				snippet = Get_sort_snippet(CmdLine, CursorPos, true)
				return Is_one_snippet(snippet)
			elseif cmd ==# 'set-encrypt'
				snippet = ['Encrypt', 'Signature', 'S/MIME', 'PGP/MIME', 'PGP', 'Subject', 'Public-Key']
			elseif cmd ==# 'set-attach' || cmd ==# 'mail-import' || cmd ==# 'mail-save'
				var dir: string = substitute(CmdLine, '^Notmuch\s\+' .. cmd .. '\s\+', '', '')
				if dir ==# ''
					snippet = glob(py3eval('os.path.expandvars(''$USERPROFILE\\'') if os.name == ''nt'' else os.path.expandvars(''$HOME/'')') .. '*', 1, 1)
				else
					if isdirectory(dir)
						dir = dir .. '/*'
					else
						dir =  dir .. '*'
					endif
					snippet = glob(dir, 1, 1)
				endif
				if len(snippet) == 1
					if isdirectory(snippet[0])
						snippet = glob(dir .. '/*', 1, 1)
					endif
				endif
			endif
		endif
	endif
	snippet = filter(snippet, printf('v:val =~? "^%s"', ArgLead))
	if len(snippet) == 0
		return []
	elseif len(snippet) == 1
		return [ snippet[0] .. ' ' ]
	else
		return snippet
	endif
enddef

export def Comp_cmd(ArgLead: string, CmdLine: string, CursorPos: number): list<any>
	return Complete_command(CmdLine, CursorPos, 0)
enddef

def Complete_command(CmdLine: string, CursorPos: number, direct_command: bool): list<any>
	var l_cmdLine: list<string> = split(CmdLine[0 : CursorPos - 1], ' ')
	var s_filter: string
	var prefix: string
	if CmdLine[CursorPos - 1] ==# ' '
		s_filter = ''
		prefix = join(l_cmdLine, ' ')
	elseif CmdLine !=? ''
		s_filter = l_cmdLine[-1]
		prefix = join(l_cmdLine[0 : -2], ' ')
	else
		s_filter = ''
		prefix = ''
	endif
	if prefix !=?  ''
		prefix = prefix .. ' '
	endif
	var cmdline: string = substitute(CmdLine, '[\n\r]\+', ' ', 'g')
	var pos: number = CursorPos + 1
	var last: list<any> = py3eval('get_last_cmd(get_mark_cmd_name(), " ' .. cmdline .. '", ' .. pos .. ')')
	var ls: list<string> = py3eval('get_mark_cmd_name()')
	if last == []
		ls = py3eval('get_mark_cmd_name()')
	else
		var cmd: string = last[0]
		var cmds: dict<any> = py3eval('get_command()')
		if cmd ==# 'mail-move'
			if last[1] # '' # 既に引数が有る
				ls = py3eval('get_mark_cmd_name()')
			else
				ls = py3eval('get_mail_folders()')
			endif
		elseif cmd ==# 'run' # -complete=shellcmd 相当のことがしたいけどやり方不明
			# ls = []
			return []
		elseif !and(cmds[cmd], 0x01) # 引数を必要としないコマンド→次のコマンドを補完対象
			ls = py3eval('get_mark_cmd_name()')
		else
			if last[1]
				ls = extend(py3eval('get_msg_all_tags_list("")'), py3eval('get_mark_cmd_name()'))
			else
				ls = py3eval('get_msg_all_tags_list("")')
			endif
		endif
	endif
	s_filter = printf('v:val =~? "^%s"', s_filter)
	var snippet_org: list<string> = filter(ls, s_filter)
	if direct_command  # input() 関数ではなく、command 直接の補完
		if len(snippet_org) == 1
			return [ snippet_org[0] .. ' ' ]
		endif
			return snippet_org
	endif
	# 補完候補にカーソル前の文字列を追加
	var snippet: list<string>
	for v in snippet_org
		add(snippet, prefix .. v)
	endfor
	if len(snippet) == 1
		return [ snippet[0] .. ' ' ]
	endif
	return snippet
enddef

function Notmuch_search(args) abort " notmuch search
	py3 notmuch_search(vim.eval('a:args'))
endfunction

def Notmuch_thread(args: list<any>): void
	py3 notmuch_thread()
enddef

def Notmuch_address(args: list<any>): void
	py3 notmuch_address()
enddef

def Notmuch_duplication(args: list<any>): void
	py3 notmuch_duplication(0)
enddef

export def Comp_search(ArgLead: string, CmdLine: string, CursorPos: number): list<any>
	var snippet: list<any> = Get_snippet('get_search_snippet', CmdLine, CursorPos, false)
	return Is_one_snippet(snippet)
enddef

export def Comp_run(ArgLead: string, CmdLine: string, CursorPos: number): list<any>
	var cmdLine: list<string> = split(CmdLine[0 : CursorPos - 1], ' ')
	var prefix: string
	var filter: string
	if CmdLine[CursorPos - 1] ==# ' '
		filter = ''
		prefix = join(cmdLine, ' ')
	elseif CmdLine !=? ''
		filter = cmdLine[-1]
		prefix = join(cmdLine[0 : -2], ' ')
	else
		filter = ''
		prefix = ''
	endif
	if prefix !=?  ''
		prefix = prefix .. ' '
	endif
	var list: list<string> =  py3eval('get_sys_command(''' .. Vim_escape('Notmuch run ' .. CmdLine) .. ''' , ''' .. Vim_escape(filter) .. ''')')
	filter = printf('v:val =~? "^%s"', filter)
	var snippet_org: list<any> = filter(list, filter)
	# 補完候補にカーソル前の文字列を追加
	var snippet: list<any>
	for v in snippet_org
		add(snippet, prefix .. v)
	endfor
	return Is_one_snippet(snippet)
enddef

def Is_one_snippet(snippet: list<string>): list<string>  # 補完候補が 1 つの場合を分ける
	if len(snippet) != 1
		return snippet
	endif
	var l_snippet = snippet[0]
	if snippet[len(snippet) - 1] ==# ':'
		return [l_snippet]
	else
		return [ l_snippet .. ' ' ]
	endif
enddef

var s_select_thread: number = -1
def Toggle_thread(args: list<any>): void
	var select_thread: number = line('.')
	if foldlevel(select_thread) == 0
		return
	elseif foldclosed(select_thread) == -1
		s_select_thread = line('.')
		normal! zC
		if foldclosed(select_thread) != -1  # 直前で再帰的に閉じたのに -1 なら単一メールのスレッド
			cursor(foldclosed(s_select_thread), 1)
		endif
	else
		select_thread = (s_select_thread <= foldclosedend(select_thread)
									&& s_select_thread >= foldclosed(select_thread)) ? s_select_thread : foldclosedend(select_thread)
		py3eval('reset_cursor_position(vim.current.buffer, ' .. select_thread .. ')')
		py3eval('fold_open()')
	endif
enddef

function Thread_change_sort(args) abort
	py3 thread_change_sort(vim.eval('a:args'))
endfunction

function Set_fcc(s) abort
	py3 set_fcc(vim.eval('a:s'))
endfunction

function Set_attach(s) abort
	py3 set_attach(vim.eval('a:s'))
endfunction

function Set_encrypt(s) abort
	py3 set_encrypt(vim.eval('a:s'))
endfunction

def Is_sametab_thread(): bool
	var type = py3eval('buf_kind()')
	if type ==# 'thread' || type ==# 'search'
		return true
	elseif type ==# 'folders' ||
				type ==# 'show' ||
				type ==# 'view'
		for b in tabpagebuflist()
			if b == get(buf_num, 'thread', 0)
				return true
			endif
			for s in values(get(buf_num, 'search', {}))
				if b == s
					return true
				endif
			endfor
		endfor
		return false
	endif
	return false
enddef

var refined_search_term: string
def Notmuch_refine(s: list<any>): void
	py3eval('notmuch_refine("' .. escape(join(s[2 : ], ' '), '"') .. '")')
enddef

def Notmuch_down_refine(dummy: list<any>): void
	py3 notmuch_down_refine()
enddef

def Notmuch_up_refine(dummy: list<any>): void
	py3 notmuch_up_refine()
enddef

export def Get_highlight(hi: string): string
	return substitute(substitute(substitute(execute('highlight ' .. hi),
				'[\n\r]\+', '', 'g'),
				' *' .. hi .. '\s\+xxx *', '', ''),
				'\%(font=\%(\w\+ \)\+\ze\w\+=\|font=\%(\w\+ \?\)\+$\)', '', '')
enddef

var fold_highlight: string = notmuch_py#Get_highlight('Folded')
var specialkey_highlight: string = notmuch_py#Get_highlight('SpecialKey')
var normal_highlight: string
if exists('g:notmuch_visible_line') && type(g:notmuch_visible_line) == 1 && g:notmuch_visible_line !=# ''
	try
		normal_highlight = notmuch_py#Get_highlight(g:notmuch_visible_line)
	catch /^Vim\%((\a\+)\)\=:E411:/
		augroup notmuch_visible_line
			autocmd!
			autocmd BufEnter * echohl WarningMsg | echomsg 'E411: highlight group not found: ' .. g:notmuch_visible_line | echomsg 'Error setting: g:notmuch_visible_line' | echohl None | autocmd! notmuch_visible_line
		augroup END
		normal_highlight = ''
	endtry
else
	normal_highlight = ''
endif

def Change_fold_highlight(): void # Folded の色変更↑highlight の保存
	if Is_sametab_thread()
		highlight Folded NONE
		if normal_highlight !=# ''
			highlight SpecialKey NONE
			execute 'silent! highlight SpecialKey ' .. normal_highlight
		endif
	else
		execute 'silent! highlight Folded ' .. fold_highlight
		if normal_highlight !=# ''
			execute 'silent! highlight SpecialKey ' .. specialkey_highlight
		endif
	endif
enddef

augroup ChangeFoldHighlight
	autocmd!
	autocmd BufEnter,WinEnter * Change_fold_highlight()
augroup END

augroup NotmuchFileType
	autocmd!
	autocmd FileType notmuch-edit setlocal syntax=notmuch-draft
	# ↑syntax の反映が setlocal filetype=xxx に引きずられる
augroup END

export def FoldThreadText(): string
	return py3eval('get_folded_list(' .. v:foldstart .. ',' .. v:foldend .. ')')
enddef

export def FoldThread(n: number): any # スレッド・リストの折畳設定
	# n Subject が何番目に表示されるのか?
	def Calculate(): dict<any>
		var i: number = 1
		var str: string
		var endl: number = line('$')
		var lines: list<string> = getbufline(bufnr('%'), 1, endl)
		var n_depth: number
		var c_depth: number
		var levels: dict<any>

		if n == 0
			str = '^[^\t]\+\t  \zs *'
		elseif n == 1
			str = '^[^\t]\+\t[^\t]\+\t  \zs *'
		elseif n == 2
			str = '^[^\t]\+\t[^\t]\+\t[^\t]\+\t  \zs *'
		endif
		n_depth = strlen(matchstr(lines[0], str)) / 2
		while i < endl
			c_depth = n_depth
			n_depth = strlen(matchstr(lines[i], str)) / 2
			if c_depth != 0
				levels[i] = c_depth + 1
			else
				if n_depth == 0
					levels[i] = 0
				else
					levels[i] = '>1'
				endif
			endif
			i += 1
		endwhile
		levels[i] = n_depth
		return levels
	enddef
	if b:changedtick != get(b:notmuch, 'changedtick', -1)
		b:notmuch.changedtick = b:changedtick
		b:notmuch.levels = Calculate()
	endif
	return b:notmuch.levels[v:lnum]
enddef

export def FoldHeaderText(): string # メールでは foldtext を変更する
	var line: string
	for l in getline(v:foldstart, '$')
		line = l
		if substitute(line, '^[ \t]\+$', '', '') !=? ''
			break
		endif
	endfor
	var cnt: string = printf('[%' .. len(line('$')) .. 's] ', (v:foldend - v:foldstart + 1))
	var line_width: number = winwidth(0) - &foldcolumn

	if &number
		line_width -= max([&numberwidth, len(line('$'))])
	# sing の表示非表示でずれる分の補正
	elseif &signcolumn ==# 'number'
		cnt = cnt .. '  '
	endif
	if &signcolumn ==# 'auto'
		cnt = cnt .. '  '
	endif
	line_width -= 2 * (&signcolumn ==# 'yes' ? 1 : 0)

	line = substitute(line, '^[\x0C]', '', '')
	line = strcharpart(printf('%s', line), 0, line_width - len(cnt))
	# 全角文字を使っていると、幅でカットすると広すぎる
	# だからといって strcharpart() の代わりに strpart() を使うと、逆に余分にカットするケースが出てくる
	# ↓末尾を 1 文字づつカットしていく
	while strdisplaywidth(line) > line_width - len(cnt)
		line = slice(line, 0, -1)
	endwhile
	return printf('%s%' .. (line_width - strdisplaywidth(line)) .. 'S', line, cnt)
enddef
