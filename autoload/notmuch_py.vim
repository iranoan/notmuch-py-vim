vim9script
# Author:  Iranoan <iranoan+vim@gmail.com>
# License: GPL Ver.3.

scriptencoding utf-8

# 下記の二重読み込み防止変数の前に取得しておかないと、途中の読み込み失敗時に設定されずに読み込むファイルの取得ができなくなる変数
var script_root: string = expand('<script>:p:h:h')
var buf_num: dict<any>

if !exists('g:loaded_notmuch_py')
	finish
endif
g:loaded_notmuch_py = 1

# Function
def DoUseNewBuffer(type: string): bool # 新規のバッファを開くか?
	# notmuch-folder の時だけバッファが空なら開き方に関係なく今のバッファをそのまま使う
	return !(
				   type ==# 'folders'
				&& wordcount().bytes == 0
				)
enddef

def NewBuffer(type: string, search_term: string): void
	if DoUseNewBuffer(type)
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
	nnoremap <buffer><silent><F1> <Cmd>topleft help notmuch-python-vim-keymap<CR>
	nnoremap <buffer><silent><leader>h <Cmd>topleft help notmuch-python-vim-keymap<CR>
	nnoremap <buffer><silent><Leader>s <Cmd>Notmuch mail-send<CR>
	nnoremap <buffer><silent><Tab> <C-w>w
	nnoremap <buffer><silent><S-Tab> <C-w>W
	nnoremap <buffer><silent><space> <Cmd>Notmuch view-unread-page<CR>
	nnoremap <buffer><silent><BS> <Cmd>Notmuch view-previous<CR>
	nnoremap <buffer><silent>J <Cmd>Notmuch view-unread-mail<CR>
	nnoremap <buffer><silent>P <Cmd>Notmuch view-previous-unread<CR>
	nnoremap <buffer><silent><C-R> <Cmd>Notmuch reload<CR>
	nnoremap <buffer><silent>p <Cmd>Notmuch mail-info<CR>
	nnoremap <buffer><silent>I <Cmd>Notmuch mail-export<CR>
	nnoremap <buffer><silent>R <Cmd>Notmuch mail-forward<CR>
	nnoremap <buffer><silent>c <Cmd>Notmuch mail-new<CR>
	nnoremap <buffer><silent>i <Cmd>Notmuch mail-import<CR>
	nnoremap <buffer><silent>r <Cmd>Notmuch mail-reply<CR>
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

def ChangeExistTabpage(type: string, search_term: string): void
	var l_buf_num: number
	if type !=? 'search' && type !=? 'view'
		l_buf_num = buf_num[type]
	else
		l_buf_num = buf_num[type][search_term]
	endif
	ChangeExistTabpageCore(l_buf_num)
enddef

def ChangeExistTabpageCore(bufnum: number): void
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

var fold_highlight: list<dict<any>> = [extend(hlget('Folded')[0], {font: ''})]
var specialkey_highlight: list<dict<any>> = [extend(hlget('SpecialKey')[0], {font: ''})]
var normal_highlight: list<dict<any>>

augroup NotmuchPython
	autocmd!
	autocmd ColorScheme * fold_highlight = [extend(hlget('Folded')[0], {font: ''})]
		| specialkey_highlight = [extend(hlget('SpecialKey')[0], {font: ''})]
	autocmd OptionSet background fold_highlight = [extend(hlget('Folded')[0], {font: ''})]
		| specialkey_highlight = [extend(hlget('SpecialKey')[0], {font: ''})]
	autocmd BufEnter,WinEnter * ChangeFoldHighlight()
	autocmd FileType notmuch-edit setlocal syntax=notmuch-draft
	# ↑syntax の反映が setlocal filetype=xxx に引きずられる
augroup END

def MakeFoldersList(): void
	if has_key(buf_num, 'folders') # && bufname(buf_num.folders) !=? ''
		ChangeExistTabpageCore(buf_num.folders)
		if bufwinid(buf_num.folders) == -1
			py3 reopen('folders', '')
		else
			win_gotoid(bufwinid(buf_num.folders))
		endif
		CloseNotmuch('thread')
		CloseNotmuch('show')
		CloseNotmuch('search')
		CloseNotmuch('view')
		var open_way: string = g:notmuch_open_way.folders
		if open_way ==# 'enew' || open_way ==# 'tabedit' || open_way != 'tabnew'
			silent only
		endif
	else
		NewBuffer('folders', '')
		var cwd: string = escape(getcwd(), "'")
		execute('silent file! notmuch://folder?' .. cwd)
		filter(v:oldfiles, 'v:val !~ ''^notmuch://folder?' .. cwd .. '''')
		py3 print_folder()
		autocmd NotmuchPython BufWipeout <buffer> ++once EndNotmuch()
	endif
enddef

def MakeThreadList(): void # スレッド・バッファを用意するだけ
	if has_key(buf_num, 'thread') # && bufname(buf_num.thread) !=? ''
		py3 reopen('thread', '')
		return
	endif
	NewBuffer('thread', '')
	SetThread(buf_num.thread)
	silent file! notmuch://thread
	filter(v:oldfiles, 'v:val !~ "^notmuch://thread"')
	autocmd NotmuchPython BufWipeout <buffer> ++once unlet buf_num.thread
	if g:notmuch_open_way.show !=? 'enew' && g:notmuch_open_way.show !=? 'tabedit' && g:notmuch_open_way.show !=? 'tabnew'
		MakeShow()
	endif
enddef

def MakeSearchList(search_term: string): void
	if has_key(buf_num.search, search_term)
		py3eval('reopen(''search'', ''' .. escape(search_term, '''\') .. ''')')
		return
	endif
	NewBuffer('search', search_term)
	var l_bufnr = bufnr()
	SetThread(l_bufnr)
	autocmd NotmuchPython BufWipeout <buffer> ++once unlet buf_num.search[b:notmuch.search_term]
	if g:notmuch_open_way.view !=? 'enew' && g:notmuch_open_way.view !=? 'tabedit' && g:notmuch_open_way.show !=? 'tabnew'
		MakeView(search_term)
	endif
enddef

def SetThread(n: number): void
	b:notmuch.tags = ''
	b:notmuch.search_term = ''
	b:notmuch.msg_id = ''
	b:notmuch.running_open_mail = false
	autocmd NotmuchPython CursorMoved <buffer> CursorMoveThread(b:notmuch.search_term)
enddef

function OpenSomething(args) abort
	py3 open_something(vim.eval('a:args'))
endfunction

def NextThread(args: list<any>): void
	var type = py3eval('buf_kind()')
	if type == 'thread' || type == 'search'
		normal! j
		py3 fold_open()
	endif
enddef

def MakeShow(): void # メール・バッファを用意するだけ
	if has_key(buf_num, 'show') # && bufname(buf_num.show) !=? ''
		py3 reopen('show', '')
		return
	endif
	NewBuffer('show', '')
	SetShow()
	silent file! notmuch://show
	filter(v:oldfiles, 'v:val !~ "^notmuch://show"')
	autocmd NotmuchPython BufWipeout <buffer> ++once unlet buf_num.show
enddef

def MakeView(search_term: string): void # メール・バッファを用意するだけ
	if has_key(buf_num.view, search_term)
		py3eval('reopen(''view'', ''' .. escape(search_term, '''\') .. ''')')
		return
	endif
	NewBuffer('view', search_term)
	var l_bufnr = bufnr()
	SetShow()
	autocmd NotmuchPython BufWipeout <buffer> ++once unlet buf_num.view[b:notmuch.search_term]
enddef

def SetShow(): void
	b:notmuch.msg_id = ''
	b:notmuch.subject = ''
	b:notmuch.date = ''
	b:notmuch.tags = ''
enddef

def SelectMailView(n: number): void
	# {F-WIN}/{T-WIN} なら {S-WIN} を選択する
	# 検索による {T-WIN} ならそれに対応する {S-WIN} を選択する
	if n == buf_num.show
		return
	elseif n == buf_num.folders
		if win_gotoid(bufwinid(buf_num.show)) == 0
			py3 reopen('show', '')
		endif
	elseif n == buf_num.thread
		if win_gotoid(bufwinid(buf_num.show)) == 0
			py3 reopen('show', '')
		endif
	elseif n == buf_num.view[b:notmuch.search_term]
		return
	elseif n == buf_num.search[b:notmuch.search_term]
		if win_gotoid(bufwinid(buf_num.view[b:notmuch.search_term])) == 0
			py3eval('reopen(''view'', ''' .. escape(b:notmuch.search_term, '''\') .. ''')')
		endif
	endif
enddef

def NextUnreadPage(args: list<any>): void # メール最後の行が表示されていればスクロールしない+既読にする
	var l_buf_num = bufnr('')
	if !has_key(buf_num, 'thread')
		MakeThreadList()
	endif
	if !has_key(buf_num, 'show')
		MakeShow()
	endif
	SelectMailView(l_buf_num)
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

def NextUnread(args: list<any>): void
	py3eval('next_unread(' .. bufnr('') .. ')')
enddef

def PreviousUnread(args: list<any>): void
	py3eval('previous_unread(' .. bufnr('') .. ')')
enddef

def PreviousPage(args: list<any>): void
	var l_buf_num = bufnr('')
	if !has_key(buf_num, 'thread')
		MakeThreadList()
	endif
	if !has_key(buf_num, 'show')
		MakeShow()
	endif
	SelectMailView(l_buf_num)
	execute 'normal! ' .. (line('w0') - 1) .. 'z-H'
	win_gotoid(bufwinid(l_buf_num))
enddef

function SaveAttachment(args) abort
	py3 save_attachment(vim.eval('a:args'))
endfunction

def ViewMailInfo(args: list<any>): void
	py3 view_mail_info()
enddef

export def ClosePopup(id: number, key: string): bool
	if key ==? 'x' || key ==? 'q' || key ==? 'c' || key ==? 'o' || key ==? 'p' || key ==? "\<Esc>"
		popup_close(id)
		return 1
	else
		return 0
	endif
enddef

function DeleteTags(args) abort
	py3 do_mail(delete_tags, vim.eval('a:args'))
endfunction

def CompleteTagCommon(func: string, cmdLine: string, cursorPos: number, direct_command: bool): list<string>
	var tags: list<string> = GetSnippet(func, cmdLine, cursorPos, direct_command)
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

def GetSnippet(func: string, cmdLine: string, cursorPos: number, direct_command: bool): list<string>  # list から cmdLine カーソル位置の単語から補完候補を取得
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

def GetSortSnippet(cmdLine: string, cursorPos: number, direct_command: bool): list<string>
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
	var ls: list<string> = ['list', 'tree', 'Date', 'date', 'Last', 'last', 'From', 'from', 'Subject', 'subject']
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

export def CompSort(ArgLead: string, CmdLine: string, CursorPos: number): list<any>
	var snippet: list<any> = GetSortSnippet(CmdLine, CursorPos, false)
	return IsOneSnippet(snippet)
enddef

export def CompDelTag(ArgLead: string, CmdLine: string, CursorPos: number): list<any>
	return CompleteTagCommon('get_msg_tags_list', CmdLine, CursorPos, false)
enddef

function AddTags(args) abort
	py3 do_mail(add_tags, vim.eval('a:args'))
endfunction

export def CompAddTag(ArgLead: string, CmdLine: string, CursorPos: number): list<any>
	return CompleteTagCommon('get_msg_tags_diff', CmdLine, CursorPos, false)
enddef

function SetTags(args) abort
	py3 do_mail(set_tags, vim.eval('a:args'))
endfunction

export def CompSetTag(ArgLead: string, CmdLine: string, CursorPos: number): list<any>
	return CompleteTagCommon('get_msg_tags_any_kind', CmdLine, CursorPos, false)
enddef

function ToggleTags(args) abort
	py3 do_mail(toggle_tags, vim.eval('a:args'))
endfunction

export def CompTag(ArgLead: string, CmdLine: string, CursorPos: number): list<any>
	return CompleteTagCommon('get_msg_all_tags_list', CmdLine, CursorPos, false)
enddef

export def Main(...arg: list<any>): void
	def Str2ls(str: string): list<string>
		var args_ls: list<string>
		var s: string = str
		var sep: list<any>

		while true
			sep = matchstrpos(s, ' *\zs\(''\(\\''\|[^'']\)\+''\|"\(\\"\|[^"]\)\+"\|[^ ]\+\)')
			add(args_ls, sep[0])
			s = strpart(s, sep[2])
			if s ==# '' || s =~# '^\s\+$'
				break
			endif
		endwhile
		return args_ls
	enddef

	if len(arg) == 2
		help notmuch-python-vim-command
		echohl WarningMsg | echomsg 'Requires argument (subcommand).' | echomsg 'open help.' | echohl None
	else
		var cmd: list<any> = [arg[0], arg[1]] + Str2ls(arg[2])
		var sub_cmd: string = remove(cmd, 2)
		if !has_key(g:notmuch_command, sub_cmd)
			help notmuch-python-vim-command
			echohl WarningMsg | echomsg 'Not exist ' .. sub_cmd .. ' subcommand.' | echomsg 'open help.' | echohl None
		else
			if sub_cmd ==# 'start'
				StartNotmuch()
			elseif sub_cmd ==# 'mail-new'
				remove(cmd, 0, 1)
				NewMail(join(cmd, ' '))
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
    from notmuchVim.subcommand import \
            add_tags, \
            buf_kind, \
            command_marked, \
            connect_thread_tree, \
            cursor_move_thread, \
            cut_thread, \
            delete_attachment, \
            delete_mail, \
            delete_tags, \
            do_mail, \
            export_mail, \
            fold_open, \
            forward_mail, \
            forward_mail_attach, \
            forward_mail_resent, \
            get_cmd_name, \
            get_cmd_name_ftype, \
            get_command, \
            get_folded_list, \
            get_hide_header, \
            get_last_cmd, \
            get_mail_folders, \
            get_mark_cmd_name, \
            get_msg_all_tags_list, \
            get_msg_id, \
            get_msg_tags_any_kind, \
            get_msg_tags_diff, \
            get_msg_tags_list, \
            get_save_dir, \
            get_save_filename, \
            get_search_snippet, \
            get_sys_command, \
            import_mail, \
            is_same_tabpage, \
            make_dump, \
            move_mail, \
            new_mail, \
            next_unread, \
            notmuch_address, \
            notmuch_down_refine, \
            notmuch_duplication, \
            notmuch_refine, \
            notmuch_search, \
            notmuch_thread, \
            notmuch_up_refine, \
            open_original, \
            open_something, \
            previous_unread, \
            print_folder, \
            reindex_mail, \
            reload, \
            reopen, \
            reply_mail, \
            reset_cursor_position, \
            run_shell_program, \
            save_attachment, \
            save_draft, \
            save_mail, \
            send_vim, \
            set_attach, \
            set_encrypt, \
            set_fcc, \
            set_forward_after, \
            set_new_after, \
            set_reply_after, \
            set_resent_after, \
            set_subcmd_newmail, \
            set_subcmd_start, \
            set_tags, \
            thread_change_sort, \
            toggle_tags, \
            view_mail_info
_EOF_
enddef

def StartNotmuch(): void
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
	MakeFoldersList()
	SetTitleEtc()
	if g:notmuch_open_way.thread !=? 'enew' && g:notmuch_open_way.thread !=? 'tabedit' && g:notmuch_open_way.show !=? 'tabnew'
		MakeThreadList()
		win_gotoid(bufwinid(buf_num.folders))
	endif
	# guifg=red ctermfg=red
	# 次の変数は Python スクリプトを読み込んでしまえばもう不要←一度閉じて再び開くかもしれない
	# unlet script_root
enddef

def CloseNotmuch(kind: string): void
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
		ChangeExistTabpageCore(b)
		if win_gotoid(bufwinid(b))
			close
		endif
	endfor
enddef

def VimEscape(s: string): string # Python に受け渡す時に \, ダブルクォートをエスケープ
	return substitute(substitute(s, '\\', '\\\\', 'g'), '''', '\\\''', 'g')
enddef

export def GetGUITabline(): string
	def GetGUITab(notmuch_dic: dict<any>): string
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
			return GetGUITab(getbufinfo(buf_num.thread)[0].variables.notmuch)
		else
			return '%{b:notmuch.subject}%<%{b:notmuch.date}'
		endif
	elseif type ==# 'view' && has_key(vars.notmuch, 'search_term')
		if py3eval('is_same_tabpage("search", ''' .. VimEscape(b:notmuch.search_term) .. ''')')
			return 'notmuch [' .. b:notmuch.search_term .. ']%<'
		else
			return '%{b:notmuch.subject}%<%{b:notmuch.date}'
		endif
	elseif type ==# 'draft'
		return 'notmuch [Draft] %{b:notmuch.subject}%<'
	elseif type ==# 'search'
		return GetGUITab(vars.notmuch)
	elseif has_key(buf_num, 'thread') # notmuch-folder では notmuch-search と同じにするのを兼ねている
		return GetGUITab(getbufinfo(buf_num.thread)[0].variables.notmuch)
	else
		return GetGUITab(vars.notmuch)
	endif
enddef

var titlestring: string = &titlestring
def SetTitleEtc(): void
	if &title
		autocmd NotmuchPython BufEnter,BufFilePost * &titlestring = MakeTitle()
	endif
	if has('gui_running') && &showtabline != 0 && &guitablabel ==# ''
		set guitablabel=%{%&filetype!~#'^notmuch-'?'%t':notmuch_py#GetGUITabline()%}
	endif
enddef

def MakeTitle(): string
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
	elseif titlestring == ''
		title = '%t %m ' .. '(' .. expand('%:~:h') .. ')'
	else
		return titlestring
	endif
	return title .. a .. ' - ' .. v:servername
enddef

def SearchNotNotmuch(): number # notmuch-? 以外のリストされていて隠れていない、もしくは隠れていても更新されているバッファを探す
	var notmuch_kind: list<string> = ['notmuch-folders', 'notmuch-thread', 'notmuch-show', 'notmuch-edit', 'notmuch-draft']
	var changed: number = 0
	for buf in getbufinfo()
		if index(notmuch_kind, getbufvar(buf.bufnr, '&filetype')) == -1
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

def EndNotmuch(): void # 全て終了 (notmuch-folders が bwipeout されたら呼ばれる)
	var bufinfo: list<dict<any>> = getbufinfo()
	var bufnr: number
	var ftype: string
	for buf in bufinfo
		bufnr = buf.bufnr
		ftype = getbufvar(bufnr, '&filetype')
		if ftype ==# 'notmuch-draft' && buf.changed || ( ftype ==# 'notmuch-edit' && buf.changed )
			SwichBuffer(bufnr)
			echohl WarningMsg | echo 'Editing ' .. ftype .. '.' | echohl None
			unlet buf_num.folders
			return
		endif
	endfor
	py3 make_dump()
	bufnr = SearchNotNotmuch()
	if bufnr == 0
		cquit # →全終了
	endif
	SwichBuffer(bufnr)
	# notmuch-* バッファ削除
	var notmuch_kind: list<string> = ['notmuch-folder', 'notmuch-thread', 'notmuch-show', 'notmuch-edit', 'notmuch-draft']
	for buf in bufinfo
		bufnr = buf.bufnr
		if index(notmuch_kind, getbufvar(bufnr, '&filetype')) != -1
			execute ':' .. bufnr .. 'bwipeout'
		endif
	endfor
	ChangeFoldHighlight()
	buf_num = {}
	s_select_thread = -1
	filter(v:oldfiles, 'v:val !~ "^notmuch://"')
	if &title
		&titlestring = MakeTitle()
	endif
enddef

def SwichBuffer(bufnr: number): void # できるだけ指定されたバッファに切り替える
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
			elseif open_way ==# 'tabedit' || open_way ==# 'tabnew'
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

function OpenOriginal(args) abort
	py3 do_mail(open_original, vim.eval('a:args'))
endfunction

def Reload(args: list<any>): void
	py3 reload()
enddef

def CursorMoveThread(search_term: string): void
	if line('.') != line('v') || b:notmuch.running_open_mail
		return
	endif
	py3eval('cursor_move_thread(''' .. escape(search_term, '''\') .. ''')')
enddef

function NewMail(...) abort
	if !py3eval('"DBASE" in globals()')  " フォルダ一覧も非表示状態で呼ばれた場合
		call s:Import()
		py3 set_subcmd_newmail()
		execute 'cd ' .. py3eval('get_save_dir()')
		if &title
			let &titlestring=s:MakeTitle()
		endif
		if has('gui_running') && &showtabline != 0 && &guitablabel ==# ''
			set guitablabel=%{%&filetype!~#'^notmuch-'?'%t':notmuch_py#GetGUITabline()%}
		endif
	endif
	py3 new_mail(vim.eval('a:000'))
endfunction

def ForwardMail(args: list<any>): void
	py3 forward_mail()
enddef

def ForwardMailAttach(args: list<any>): void
	py3 forward_mail_attach()
enddef

def ForwardMailResent(args: list<any>): void
	py3 forward_mail_resent()
enddef

def ReplyMail(args: list<any>): void
	py3 reply_mail()
enddef

def SendVim(args: list<any>): void
	py3 send_vim()
enddef

function SaveMail(args) abort
	if len(a:args) > 3
		py3 do_mail(save_mail, vim.eval('a:args[:2]'))
	else
		py3 do_mail(save_mail, vim.eval('a:args'))
	endif
endfunction

function MoveMail(args) abort
	py3 do_mail(move_mail, vim.eval('a:args'))
endfunction

export def CompDir(ArgLead: string, CmdLine: string, CursorPos: number): list<any>
	var folders: list<any> = py3eval('get_mail_folders()')
	return filter(folders, printf('v:val =~? "^%s"', ArgLead))
enddef

function RunShellProgram(args) abort
	py3 do_mail(run_shell_program, vim.eval('a:args'))
endfunction

function ReindexMail(args) abort
	py3 do_mail(reindex_mail, vim.eval('a:args'))
endfunction

function ImportMail(args) abort
	py3 import_mail(vim.eval('a:args'))
endfunction

function DeleteMail(args) abort
	py3 do_mail(delete_mail, vim.eval('a:args'))
endfunction

function ExportMail(args) abort
	py3 do_mail(export_mail, vim.eval('a:args'))
endfunction

function DeleteAttachment(args) abort
	py3 delete_attachment(vim.eval('a:args'))
endfunction

def CloseCore(): void # notmuch-* を閉じる (閉じるメイン部分)
	if winnr('$') == 1 && tabpagenr('$') == 1
		var bufnr: number = SearchNotNotmuch()
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

	def ClosePairCore(pair_b: number)
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

	def ClosePair(buf_dic: dict<any>, s: string)
		if !has_key(buf_dic, s)
			CloseCore()
			return
		endif
		ClosePairCore(buf_dic[s])
	enddef

	def ClosePairSearch(buf_dic: dict<any>, k: string): void
		var s: string = b:notmuch.search_term
		if get(buf_num[k], s, 0) != bufnum
			return
		endif
		var pair_k: string = {search: 'view', view: 'search'}[k]
		if !has_key(buf_dic, pair_k)
			CloseCore()
		elseif !has_key(buf_dic[pair_k], s)
			CloseCore()
		else
			ClosePairCore(buf_dic[pair_k][s])
		endif
	enddef

	for b in tabpagebuflist()
		if b == buf_num.folders
			execute 'bwipeout ' .. b
			return
		endif
	endfor
	if &filetype ==# 'notmuch-edit' || &filetype ==# 'notmuch-draft'
		close
	elseif get(buf_num, 'thread', 0) == bufnum
		ClosePair(buf_num, 'show')
	elseif get(buf_num, 'show', 0)  == bufnum
		ClosePair(buf_num, 'thread')
	elseif &filetype ==# 'notmuch-thread'
		ClosePairSearch(buf_num, 'search')
	elseif &filetype ==#  'notmuch-show'
		ClosePairSearch(buf_num, 'view')
	endif
enddef

def AuEdit(win: number, search_term: string, reload: bool): void # 閉じた時の処理 (呼び出し元に戻り reload == true で notmuch-show, notmuch-view が同じタブページに有れば再読込)
	var l_bufnr = bufnr()
	execute 'autocmd NotmuchPython BufWinLeave <buffer> ++once ChangeExistTabpageCore(' .. win .. ') |' ..
		(reload ?
			(search_term ==# '' ? 'if py3eval(''is_same_tabpage("show", "")'') |'
			: 'if py3eval(''is_same_tabpage(''''view'''', ''''' .. escape(search_term, '''\') .. ''''')'') |') ..
					'win_gotoid(bufwinid(buf_num["show"])) | ' ..
					'Reload([]) |' ..
				'endif | '
		: '') ..
		'win_gotoid(bufwinid(' .. win .. '))'
enddef

def AuNewMail(): void # 新規/添付転送メールでファイル末尾移動時に From 設定や署名の挿入
	autocmd NotmuchPython CursorMoved,CursorMovedI <buffer> py3eval('set_new_after()')
enddef

def AuReplyMail(): void # 返信メールでファイル末尾移動時に From 設定や署名・返信元引用文の挿入
	autocmd NotmuchPython CursorMoved,CursorMovedI <buffer> py3eval('set_reply_after()')
enddef

def AuForwardMail(): void # 転送メールでファイル末尾移動時に From 設定や署名・転送元の挿入
	autocmd NotmuchPython CursorMoved,CursorMovedI <buffer> py3eval('set_forward_after()')
enddef

def AuResentMail(): void # 転送メールでファイル末尾移動時に From 設定や署名・転送元の挿入
	autocmd NotmuchPython CursorMoved,CursorMovedI <buffer> py3eval('set_resent_after()')
enddef

def AuWriteDraft(): void # draft mail の保存
	autocmd NotmuchPython BufWrite <buffer> py3 save_draft()
enddef

function MarkInThread(args) range abort
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

def CutThread(args: list<any>): void
	py3 cut_thread(get_msg_id(), [])
enddef

def ConnectThread(args: list<any>): void
	py3 connect_thread_tree()
enddef

function CommandMarked(args) abort " マークしたメールに纏めてコマンド実行
	call remove(a:args, 0, 1)
	py3 command_marked(vim.eval('a:args'))
endfunction

export def CompAllArgs(ArgLead: string, CmdLine: string, CursorPos: number): list<any>
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
				return CompleteCommand(strpart(CmdLine, index), CursorPos - index, true)
			elseif cmd ==# 'run'
				snippet = py3eval('get_sys_command(''' .. VimEscape(CmdLine) .. ''' , ''' .. VimEscape(ArgLead) .. ''')')
			elseif cmd ==# 'mail-move' || cmd ==# 'set-fcc'
				if last[1] # 既にサブ・コマンドの引数が有る
					return []
				endif
				snippet = py3eval('get_mail_folders()')
			elseif cmd ==# 'tag-add'
				return CompleteTagCommon('get_msg_tags_diff', CmdLine, CursorPos, true)
			elseif cmd ==# 'tag-delete'
				return CompleteTagCommon('get_msg_tags_list', CmdLine, CursorPos, true)
			elseif cmd ==# 'tag-set'
				return CompleteTagCommon('get_msg_tags_any_kind', CmdLine, CursorPos, true)
			elseif cmd ==# 'tag-toggle'
				return CompleteTagCommon('get_msg_all_tags_list', CmdLine, CursorPos, true)
			elseif cmd ==# 'search' || cmd ==# 'search-refine'
				snippet = GetSnippet('get_search_snippet', CmdLine, CursorPos, true)
				return IsOneSnippet(snippet)
			elseif cmd ==# 'thread-sort'
				snippet = GetSortSnippet(CmdLine, CursorPos, true)
				return IsOneSnippet(snippet)
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

export def CompCmd(ArgLead: string, CmdLine: string, CursorPos: number): list<any>
	return CompleteCommand(CmdLine, CursorPos, 0)
enddef

def CompleteCommand(CmdLine: string, CursorPos: number, direct_command: bool): list<any>
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
		elseif cmd ==# 'run'
			ls = py3eval('get_sys_command(''mark_cmd ' .. VimEscape(cmdline) .. ''' , ''' .. VimEscape(s_filter) .. ''')')
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

function NotmuchSearch(args) abort " notmuch search
	py3 notmuch_search(vim.eval('a:args'))
endfunction

def NotmuchThread(args: list<any>): void
	py3 notmuch_thread()
enddef

def NotmuchAddress(args: list<any>): void
	py3 notmuch_address()
enddef

def NotmuchDuplication(args: list<any>): void
	py3 notmuch_duplication(0)
enddef

export def CompSearch(ArgLead: string, CmdLine: string, CursorPos: number): list<any>
	var snippet: list<any> = GetSnippet('get_search_snippet', CmdLine, CursorPos, false)
	return IsOneSnippet(snippet)
enddef

export def CompRun(ArgLead: string, CmdLine: string, CursorPos: number): list<any>
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
	var list: list<string> = py3eval('get_sys_command(''' .. VimEscape('Notmuch run ' .. CmdLine) .. ''' , ''' .. VimEscape(filter) .. ''')')
	filter = printf('v:val =~? "^%s"', filter)
	var snippet_org: list<any> = filter(list, filter)
	# 補完候補にカーソル前の文字列を追加
	var snippet: list<any>
	for v in snippet_org
		add(snippet, prefix .. v)
	endfor
	return IsOneSnippet(snippet)
enddef

def IsOneSnippet(snippet: list<string>): list<string>  # 補完候補が 1 つの場合を分ける
	if len(snippet) != 1
		return snippet
	endif
	if snippet[0] =~# '[: ]$'
		return snippet
	else
		return [snippet[0] .. ' ']
	endif
enddef

var s_select_thread: number = -1
def ToggleThread(args: list<any>): void
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

function ThreadChangeSort(args) abort
	py3 thread_change_sort(vim.eval('a:args'))
endfunction

function SetFcc(s) abort
	py3 set_fcc(vim.eval('a:s'))
endfunction

function SetAttach(s) abort
	py3 set_attach(vim.eval('a:s'))
endfunction

function SetEncrypt(s) abort
	py3 set_encrypt(vim.eval('a:s'))
endfunction

def IsSametabThread(): bool
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
def NotmuchRefine(s: list<any>): void
	py3eval('notmuch_refine("' .. escape(join(s[2 : ], ' '), '"') .. '")')
enddef

def NotmuchDownRefine(dummy: list<any>): void
	py3 notmuch_down_refine()
enddef

def NotmuchUpRefine(dummy: list<any>): void
	py3 notmuch_up_refine()
enddef

export def ChangeColorColumn(): void
	hlset([hlget('Normal')[0]->extend({name: 'ColorColumn', font: '', term: {reverse: true}, cterm: {reverse: true}, gui: {reverse: true}})])
enddef

if exists('g:notmuch_visible_line') && type(g:notmuch_visible_line) == 1 && g:notmuch_visible_line !=# ''
	try
		normal_highlight = [extend(hlget(g:notmuch_visible_line)[0], {font: ''})]
	catch /^Vim\%((\a\+)\)\=:E411:/
		autocmd NotmuchPython BufEnter * ++once echohl WarningMsg | echomsg 'E411: highlight group not found: ' .. g:notmuch_visible_line | echomsg 'Error setting: g:notmuch_visible_line' | echohl None
		normal_highlight = []
	endtry
else
	normal_highlight = []
endif

def ChangeFoldHighlight(): void # Folded の色変更↑highlight の保存
	if IsSametabThread()
		highlight Folded NONE
		if normal_highlight !=# []
			highlight SpecialKey NONE
			hlset(normal_highlight)
		endif
	else
		hlset(fold_highlight)
		if normal_highlight !=# []
			hlset(specialkey_highlight)
		endif
	endif
enddef

export def FoldThreadText(): string
	return py3eval('get_folded_list(' .. v:foldstart .. ',' .. v:foldend .. ')')
enddef

export def FoldThread(n: number): any # スレッド・リストの折畳設定
	# n Subject が何番目に表示されるのか?
	var str: string
	var n_depth: number
	var c_depth: number

	if n == 0
		str = '^[^\t]\+\t  \zs *'
	elseif n == 1
		str = '^[^\t]\+\t[^\t]\+\t  \zs *'
	elseif n == 2
		str = '^[^\t]\+\t[^\t]\+\t[^\t]\+\t  \zs *'
	endif
	c_depth = strlen(matchstr(getbufoneline(bufnr('%'), v:lnum), str)) / 2
	if c_depth != 0
		return c_depth + 1
	else
		n_depth = strlen(matchstr(getbufoneline(bufnr('%'), v:lnum + 1), str)) / 2
		if n_depth == 0
			return 0
		else
			return '>1'
		endif
	endif
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
