" Author:  Iranoan <iranoan+vim@gmail.com>
" License: GPL Ver.3.

scriptencoding utf-8
scriptversion 4

" 下記の二重読み込み防止変数の前に取得しておかないと、途中の読み込み失敗時に設定されずに読み込むファイルの取得ができなくなる変数
let s:script_root = expand('<sfile>:p:h:h')

if !exists('g:loaded_notmuch_py')
	finish
endif
let g:loaded_notmuch_py = 1

" Function
function s:do_use_new_buffer(type) abort " 新規のバッファを開くか?
	" notmuch-folder の時だけバッファが空なら開き方に関係なく今のバッファをそのまま使う
	return !(
				\    a:type ==# 'folders'
				\ && wordcount().bytes == 0
				\ )
endfunction

function s:new_buffer(type, search_term) abort
	if s:do_use_new_buffer(a:type)
		try
			execute g:notmuch_open_way[a:type]
		catch /^Vim\%((\a\+)\)\=:E36:/
			echomsg 'execute only command'
			call win_gotoid(bufwinid(s:buf_num.folders))
			silent only
			execute g:notmuch_open_way[a:type]
		endtry
	endif
	if a:type !=? 'search' && a:type !=? 'view'
		let s:buf_num[a:type] = bufnr('')
		let b:notmuch = {}
	else
		let s:buf_num[a:type][a:search_term] = bufnr('')
		let b:notmuch = {}
	endif
	" キーマップ
	" draft/edit 以外共通
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
	if a:type ==# 'folders'
		setlocal filetype=notmuch-folders
	elseif a:type ==# 'thread' || a:type ==# 'search'
		setlocal filetype=notmuch-thread
	elseif a:type ==# 'show' || a:type ==# 'view'
		setlocal filetype=notmuch-show
	endif
	setlocal modifiable buftype=nofile bufhidden=hide noequalalways fileencoding=utf-8 noswapfile
	keepjumps 0d
endfunction

function s:change_exist_tabpage(type, search_term) abort
	if a:type !=? 'search' && a:type !=? 'view'
		let l:buf_num = s:buf_num[a:type]
	else
		let l:buf_num = s:buf_num[a:type][a:search_term]
	endif
	call s:change_exist_tabpage_core(l:buf_num)
endfunction

function s:change_exist_tabpage_core(bufnum) abort
	let l:tabpage = 0
	for l:i in range(tabpagenr('$'))
		if match(tabpagebuflist(l:i + 1), a:bufnum) != -1
			let l:tabpage = l:i + 1
			break
		endif
	endfor
	if l:tabpage != 0 " タブページが有る場合
		execute l:tabpage .. 'tabnext'
	endif
endfunction

function s:make_folders_list() abort
	if has_key(s:buf_num, 'folders') " && bufname(s:buf_num.folders) !=? ''
		call s:change_exist_tabpage_core(s:buf_num.folders)
		if bufwinid(s:buf_num.folders) == -1
			py3 reopen('folders', '')
		else
			call win_gotoid(bufwinid(s:buf_num.folders))
		endif
		call s:close_notmuch('thread')
		call s:close_notmuch('show')
		call s:close_notmuch('search')
		call s:close_notmuch('view')
		let open_way = g:notmuch_open_way.folders
		if open_way ==# 'enew' || open_way ==# 'tabedit'
			silent only
		endif
	else
		call s:new_buffer('folders', '')
		silent file! notmuch-folder
		py3 print_folder()
		augroup NotmuchMakeFolder
			autocmd!
			autocmd BufWipeout <buffer> call s:end_notmuch()
		augroup END
	endif
endfunction

function s:make_thread_list() abort " スレッド・バッファを用意するだけ
	if has_key(s:buf_num, 'thread') " && bufname(s:buf_num.thread) !=? ''
		py3 reopen('thread', '')
		return
	endif
	call s:new_buffer('thread', '')
	silent file! notmuch-thread
	call s:set_thread()
	augroup NotmuchMakeThread
		autocmd!
		autocmd BufWipeout <buffer> unlet s:buf_num.thread
	augroup END
	if g:notmuch_open_way.show !=? 'enew' && g:notmuch_open_way.show !=? 'tabedit'
		call s:make_show()
	endif
endfunction

function s:make_search_list(search_term) abort
	if has_key(s:buf_num.search, a:search_term)
		py3 reopen('search', vim.bindeval('a:search_term'))
		return
	endif
	call s:new_buffer('search', a:search_term)
	let l:s = substitute(a:search_term, '"', '\\"', 'g')
	execute 'silent file! notmuch-thread [' .. l:s .. ']'
	call s:set_thread()
	augroup NotmuchMakeSearch
		" autocmd! 残しておくと他の検索方法を実行した時に、キャンセルされてしまう
		autocmd BufWipeout <buffer> unlet s:buf_num.search[b:notmuch.search_term]
	augroup END
	if g:notmuch_open_way.view !=? 'enew' && g:notmuch_open_way.view !=? 'tabedit'
		call s:make_view(a:search_term)
	endif
endfunction

function s:set_thread() abort
	let b:notmuch.tags = ''
	let b:notmuch.search_term = ''
	let b:notmuch.msg_id = ''
	augroup NotmuchSetThread
		" autocmd! 残しておくと他の検索方法を実行した時に、キャンセルされてしまう
		autocmd CursorMoved <buffer> call s:cursor_move_thread(b:notmuch.search_term)
	augroup END
endfunction

function s:open_something(args) abort
	let l:type = py3eval('buf_kind()')
	if l:type ==# 'folders'
		" let l:s = reltime()
		call s:open_thread(v:true, v:false)
		" echomsg reltimestr(reltime(l:s))
	elseif l:type ==# 'thread' || l:type ==# 'search'
		call s:open_mail()
	elseif l:type ==# 'show' || l:type ==# 'view'
		py3 open_attachment(vim.eval('a:args'))
	endif
endfunction

function s:open_thread(select_unread, remake) abort " 実際にスレッドを印字←フォルダ・リストがアクティブ前提
	let l:line = line('.')
	call s:make_thread_list()
	py3 open_thread(vim.bindeval('l:line'), vim.bindeval('a:select_unread'), vim.bindeval('a:remake'))
	if py3eval('is_same_tabpage("show", "")')
		call s:open_mail()
	endif
endfunction

function s:make_show() abort " メール・バッファを用意するだけ
	if has_key(s:buf_num, 'show') " && bufname(s:buf_num.show) !=? ''
		py3 reopen('show','')
		return
	endif
	call s:new_buffer('show', '')
	call s:set_show()
	silent file! notmuch-show
	augroup NotmuchMakeShow
		autocmd!
		autocmd BufWipeout <buffer> unlet s:buf_num.show
	augroup END
endfunction

function s:make_view(search_term) abort " メール・バッファを用意するだけ
	if has_key(s:buf_num.view, a:search_term)
		py3 reopen('view', vim.eval('a:search_term'))
		return
	endif
	call s:new_buffer('view', a:search_term)
	let l:s = substitute(a:search_term, '"', '\\"', 'g')
	execute 'silent file! notmuch-show [' .. l:s .. ']'
	call s:set_show()
	augroup NotmuchMakeView
		" autocmd!
		autocmd BufWipeout <buffer> unlet s:buf_num.view[b:notmuch.search_term]
	augroup END
endfunction

function s:set_show() abort
	let b:notmuch.msg_id = ''
	let b:notmuch.subject = ''
	let b:notmuch.date = ''
	let b:notmuch.tags = ''
endfunction

function s:open_mail() abort
	if b:notmuch.search_term ==# '' || getline('.') ==# ''
		if py3eval('is_same_tabpage("show", "")')
			py3 empty_show()
		endif
		return
	endif
	let l:mail_index = line('.') - 1
	let l:search_term = b:notmuch.search_term
	let l:buf_num = bufnr('')
	py3 open_mail(vim.eval('l:search_term'), vim.bindeval('l:mail_index'), vim.eval('l:buf_num'))
endfunction

function s:next_unread_page(args) abort " メール最後の行が表示されていればスクロールしない+既読にする
	let l:buf_num = bufnr('')
	if !has_key(s:buf_num, 'thread')
		call s:make_thread_list()
	endif
	if !has_key(s:buf_num, 'show')
		call s:make_show()
	endif
	if win_gotoid(bufwinid(s:buf_num.show)) == 0
		if has_key(s:buf_num, 'view')
					\ && has_key(b:notmuch, 'search_term')
					\ && b:notmuch.search_term !=# ''
					\ && has_key(s:buf_num.view, b:notmuch.search_term)
			call win_gotoid(bufwinid(s:buf_num.view[b:notmuch.search_term]))
		else
			py3 reopen('show', '')
		endif
	endif
	if !exists('b:notmuch.msg_id') || b:notmuch.msg_id ==# ''
		py3 next_unread(vim.eval('l:buf_num'))
		return
	endif
	if line('w$') == line('$') " 最終行表示
		let l:column = col('.')
		if line('w0') == line('w$') " 最終行表示でも 表示先頭行=表示最終行 なら折り返し部分が非表示の可能性→カーソル移動
			execute 'normal!' 2 * winheight(0) - winline() - 1 .. 'gj'
			if l:column == col('.')
				py3 delete_tags(vim.current.buffer.vars['notmuch']['msg_id'].decode(), '', [0, 0, 'unread'])
				py3 next_unread(vim.eval('l:buf_num'))
			endif
		else
			py3 delete_tags(vim.current.buffer.vars['notmuch']['msg_id'].decode(), '', [0, 0, 'unread'])
			py3 next_unread(vim.eval('l:buf_num'))
		endif
	elseif line('w0') != line('w$') " 一行で 1 ページ全体だと、<PageDown> では折り返されている部分が飛ばされるので分ける
		execute "normal! \<PageDown>"
		if line('w0') != line('w$') && line('w$') == line('$') " 表示先頭行 != 最終行 かつ 表示最終行 = 最終行 なら最後まで表示
			py3 delete_tags(vim.current.buffer.vars['notmuch']['msg_id'].decode(), '', [0, 0, 'unread'])
		endif
	else
		let l:pos=line('.')
		execute 'normal!' winheight(0) - winline() + 1 .. 'gj'
		if line('.') != l:pos " 移動前に表示していた次の行までカーソル移動して、行番号が異なれば行の最後まで表示されていた
			call cursor(l:pos,0) " 一旦前の位置に移動し次で次行を画面最上部に表示
			normal! jzt
		else " 行の途中まで表示していた
			execute 'normal!' winheight(0) - 2 .. 'gj'
			" ↑追加で 1 ページ分カーソル移動←本当はページ先頭に戻したいがやり方がわからない
			if line('.') != l:pos " カーソル移動して行番号異なれば、以降の行まで移動した
				call cursor(l:pos,0) " 一旦前の位置に移動し次で行末の表示先頭桁に移動
				normal! $g^
			endif
		endif
	endif
	call win_gotoid(bufwinid(l:buf_num))
endfunction

function s:next_unread(args) abort
	py3 next_unread(vim.eval('bufnr("")'))
endfunction

function s:previous_page(args) abort
	let l:buf_num = bufnr('')
	if !has_key(s:buf_num, 'thread')
		call s:make_thread_list()
	endif
	if !has_key(s:buf_num, 'show')
		call s:make_show()
	endif
	if win_gotoid(bufwinid(s:buf_num.show)) == 0
		if has_key(s:buf_num, 'view')
					\ && has_key(b:notmuch, 'search_term')
					\ && b:notmuch.search_term !=# ''
					\ && has_key(s:buf_num.view, b:notmuch.search_term)
			call win_gotoid(bufwinid(s:buf_num.view[b:notmuch.search_term]))
		else
			py3 reopen('show', '')
		endif
	endif
	execute "normal! \<PageUp>"
	call win_gotoid(bufwinid(l:buf_num))
endfunction

function s:save_attachment(args) abort
	py3 save_attachment(vim.eval('a:args'))
endfunction

function s:view_mail_info(args) abort
	py3 view_mail_info()
endfunction

function s:close_popup(id, key) abort
	if a:key ==? 'x' || a:key ==? 'q' || a:key ==? 'c' || a:key ==? 'p' || a:key ==? "\<Esc>"
		call popup_close(a:id)
		return 1
	else
		return 0
	endif
endfunction

function s:delete_tags(args) abort
	py3 do_mail(delete_tags, vim.eval('a:args'))
endfunction

function s:complete_tag_common(func, cmdLine, cursorPos, direct_command) abort
	let l:tags = s:get_snippet(a:func, a:cmdLine, a:cursorPos, a:direct_command)
	for l:t in split(a:cmdLine)[2:]
		let l:filter = printf('v:val !~ "^%s\\>"', l:t)
		let l:tags = filter(l:tags, l:filter)
	endfor
	if len(l:tags) != 1
		return l:tags
	endif
	return [ l:tags[0] .. ' ' ]
endfunction

function s:get_snippet(func, cmdLine, cursorPos, direct_command) abort  " list から cmdLine カーソル位置の単語から補完候補を取得
	let l:cmdLine = split(a:cmdLine[0:a:cursorPos-1], ' ')
	if a:cmdLine[a:cursorPos-1] ==# ' '
		let l:filter = ''
		let l:prefix = join(l:cmdLine, ' ')
	elseif a:cmdLine !=? ''
		let l:filter = l:cmdLine[-1]
		let l:prefix = join(l:cmdLine[0:-2], ' ')
	else
		let l:filter = ''
		let l:prefix = ''
	endif
	if l:prefix !=?  ''
		let l:prefix = l:prefix .. ' '
	endif
	let l:list = py3eval(a:func .. '("' .. substitute(l:filter, '"', '\\"', 'g') .. '")')
	let l:filter = printf('v:val =~ "^%s"', l:filter)
	let l:snippet_org = filter(l:list, l:filter)
	if a:direct_command  " input() 関数ではなく、command 直接の補完
		return l:snippet_org
	endif
	" 補完候補にカーソル前の文字列を追加
	let l:snippet = []
	for l:v in l:snippet_org
		call add(l:snippet, l:prefix .. l:v)
	endfor
	return l:snippet
endfunction

function s:get_sort_snippet(cmdLine, cursorPos, direct_command) abort
	let l:cmdLine = split(a:cmdLine[0:a:cursorPos-1], ' ')
	echomsg l:cmdLine
	if a:cmdLine[a:cursorPos-1] ==# ' '
		let l:filter = ''
		let l:prefix = join(l:cmdLine, ' ')
	elseif a:cmdLine !=? ''
		let l:filter = l:cmdLine[-1]
		let l:prefix = join(l:cmdLine[0:-2], ' ')
	else
		let l:filter = ''
		let l:prefix = ''
	endif
	if l:prefix !=?  ''
		let l:prefix = l:prefix .. ' '
	endif
	let l:list = ['list', 'tree', 'Date', 'date', 'From', 'from', 'Subject', 'subject']
	let l:filter = printf('v:val =~# "^%s"', l:filter)
	let l:snippet_org = filter(l:list, l:filter)
	if a:direct_command  " input() 関数ではなく、command 直接の補完
		return l:snippet_org
	endif
	" 補完候補にカーソル前の文字列を追加
	let l:snippet = []
	for l:v in l:snippet_org
		call add(l:snippet, l:prefix .. l:v)
	endfor
	return l:snippet
endfunction

function notmuch_py#comp_sort(ArgLead, CmdLine, CursorPos) abort
	let l:snippet = s:get_sort_snippet(a:CmdLine, a:CursorPos, v:false)
	return s:is_one_snippet(l:snippet)
endfunction

function notmuch_py#comp_del_tag(ArgLead, CmdLine, CursorPos) abort
	return s:complete_tag_common('get_msg_tags_list', a:CmdLine, a:CursorPos, v:false)
endfunction

function s:add_tags(args) abort
	py3 do_mail(add_tags, vim.eval('a:args'))
endfunction

function notmuch_py#comp_add_tag(ArgLead, CmdLine, CursorPos) abort
	return s:complete_tag_common('get_msg_tags_diff', a:CmdLine, a:CursorPos, v:false)
endfunction

function s:set_tags(args) abort
	py3 do_mail(set_tags, vim.eval('a:args'))
endfunction

function notmuch_py#comp_set_tag(ArgLead, CmdLine, CursorPos) abort
	return s:complete_tag_common('get_msg_tags_any_kind', a:CmdLine, a:CursorPos, v:false)
endfunction

function s:toggle_tags(args) abort
	py3 do_mail(toggle_tags, vim.eval('a:args'))
endfunction

function notmuch_py#comp_tag(ArgLead, CmdLine, CursorPos) abort
	return s:complete_tag_common('get_msg_all_tags_list', a:CmdLine, a:CursorPos, v:false)
endfunction

function notmuch_py#notmuch_main(...) abort
	if a:0 == 2
		help notmuch-python-vim-command
		echohl WarningMsg | echomsg 'Requires argument (subcommand).' | echomsg 'open help.' | echohl None
	else
		let l:cmd = copy(a:000)
		let l:sub_cmd = remove(l:cmd, 2)
		if !has_key(g:notmuch_command, l:sub_cmd)
			help notmuch-python-vim-command
			echohl WarningMsg | echomsg 'Not exist ' .. l:sub_cmd .. ' subcommand.' | echomsg 'open help.' | echohl None
		else
			if l:sub_cmd ==# 'start'
				call s:start_notmuch()
			elseif l:sub_cmd ==# 'mail-new'
				call remove(l:cmd, 0, 1)
				call s:new_mail(join(l:cmd, ' '))
			else
				execute 'call ' .. g:notmuch_command[l:sub_cmd][0] .. '(l:cmd)'
			endif
		endif
	endif
endfunction

function s:import()
	python3 << _EOF_
import os, sys, vim
if 'notmuchVim' not in sys.modules:
    if not vim.eval('s:script_root') + '/autoload/' in sys.path:
        sys.path.append(vim.eval('s:script_root') + '/autoload/')
    import notmuchVim
    # vim から呼び出す関数は関数名だけで呼び出せるようにする
    from notmuchVim.subcommand import add_tags
    from notmuchVim.subcommand import buf_kind
    from notmuchVim.subcommand import change_buffer_vars
    from notmuchVim.subcommand import command_marked
    from notmuchVim.subcommand import connect_thread_tree
    from notmuchVim.subcommand import cut_thread
    from notmuchVim.subcommand import delete_attachment
    from notmuchVim.subcommand import delete_mail
    from notmuchVim.subcommand import delete_tags
    from notmuchVim.subcommand import do_mail
    from notmuchVim.subcommand import empty_show
    from notmuchVim.subcommand import export_mail
    from notmuchVim.subcommand import forward_mail
    from notmuchVim.subcommand import forward_mail_attach
    from notmuchVim.subcommand import forward_mail_resent
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
    from notmuchVim.subcommand import get_cmd_name
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
    from notmuchVim.subcommand import open_attachment
    from notmuchVim.subcommand import open_mail
    from notmuchVim.subcommand import open_original
    from notmuchVim.subcommand import open_thread
    from notmuchVim.subcommand import print_folder
    from notmuchVim.subcommand import reindex_mail
    from notmuchVim.subcommand import reload_show
    from notmuchVim.subcommand import reload_thread
    from notmuchVim.subcommand import reopen
    from notmuchVim.subcommand import reply_mail
    from notmuchVim.subcommand import reset_cursor_position
    from notmuchVim.subcommand import run_shell_program
    from notmuchVim.subcommand import save_attachment
    from notmuchVim.subcommand import save_draft
    from notmuchVim.subcommand import send_vim
    from notmuchVim.subcommand import set_attach
    from notmuchVim.subcommand import set_encrypt
    from notmuchVim.subcommand import set_fcc
    from notmuchVim.subcommand import set_forward_after
    from notmuchVim.subcommand import set_new_after
    from notmuchVim.subcommand import set_reply_after
    from notmuchVim.subcommand import set_resent_after
    from notmuchVim.subcommand import set_tags
    from notmuchVim.subcommand import thread_change_sort
    from notmuchVim.subcommand import toggle_tags
    from notmuchVim.subcommand import view_mail_info
    from notmuchVim.subcommand import set_subcmd_start
    from notmuchVim.subcommand import set_subcmd_newmail
_EOF_
endfunction

function s:start_notmuch() abort
	let s:pop_id = 0
	if !exists('s:buf_num')
		let s:buf_num = {}
	endif
	if !has_key(s:buf_num, 'search')
		let s:buf_num.search = {}
	endif
	if !has_key(s:buf_num, 'view')
		let s:buf_num.view = {}
	endif
	call s:import()
	py3 set_subcmd_start()
	execute 'cd ' .. py3eval('get_save_dir()')
	call s:make_folders_list()
	call s:set_title_etc()
	if g:notmuch_open_way.thread !=? 'enew' && g:notmuch_open_way.thread !=? 'tabedit'
		call s:make_thread_list()
		call win_gotoid(bufwinid(s:buf_num.folders))
	endif
	" guifg=red ctermfg=red
	" 次の変数は Python スクリプトを読み込んでしまえばもう不要←一度閉じて再び開くかもしれない
	" unlet s:script_root
endfunction

function s:close_notmuch(kind) abort
	if !has_key(s:buf_num, a:kind)
		return
	endif
	if a:kind ==# 'thread' || a:kind ==# 'show'
		let l:bufs = [s:buf_num[a:kind]]
	else
		let l:bufs = values(s:buf_num[a:kind])
	endif
	for l:b in l:bufs
		call s:change_exist_tabpage_core(l:b)
		if win_gotoid(bufwinid(l:b))
			close
		endif
	endfor
endfunction

function s:vim_escape(s) abort " Python に受け渡す時に \, ダブルクォートをエスケープ
	return substitute(substitute(a:s, '\\', '\\\\', 'g'), '''', '\\\''', 'g')
endfunction

function! MakeGUITabline() abort
	let l:bufnrlist = tabpagebuflist(v:lnum)
	" ウィンドウが複数あるときにはその数を追加する
	let l:wincount = tabpagewinnr(v:lnum, '$')
	if l:wincount > 1
		let l:label = l:wincount
	else
		let l:label = ''
	endif
	" このタブページに変更のあるバッファは '+' を追加する
	for l:bufnr in l:bufnrlist
		if getbufvar(l:bufnr, '&modified')
					\ && !( match(getbufinfo(l:bufnr)[0].name, '!/') == 0 && swapname(l:bufnr) ==# '' )
					" 名前が !/bin/bash 等で !/ ではじまり、スワップ・ファイルがなければ :terminal の可能性が高い
			let l:label ..= '+'
			break
		endif
	endfor
	if l:label !=? ''
		let l:label ..= ' '
	endif
	" バッファ名を追加する
	if &filetype !~# '^notmuch-'
		return '%N|' .. l:label .. ' %t'
	else
		let l:type = py3eval('buf_kind()')
		let l:vars = getbufinfo(bufnr())[0].variables
		if l:type ==# 'edit'
			return '%N| ' .. l:label .. '%{b:notmuch.subject} %{b:notmuch.date}'
		elseif l:type ==# 'show'
			if py3eval('is_same_tabpage("thread", "")')
				return s:get_gui_tab(getbufinfo(s:buf_num.thread)[0].variables.notmuch)
			else
				return '%N| ' .. l:label .. '%{b:notmuch.subject} %{b:notmuch.date}'
			endif
		elseif l:type ==# 'view' && has_key(l:vars.notmuch, 'search_term')
			if py3eval('is_same_tabpage("search", ''' .. s:vim_escape(b:notmuch.search_term) .. ''')')
				return '%N| notmuch [' .. b:notmuch.search_term .. ']%<'
			else
				return '%N| ' .. l:label .. '%{b:notmuch.subject} %{b:notmuch.date}'
			endif
		elseif l:type ==# 'draft'
			" return '%N| ' .. l:label .. 'notmuch %t %{b:notmuch.subject}%<'
			return '%N| ' .. l:label .. 'notmuch [Draft] %{b:notmuch.subject}%<'
		elseif l:type ==# 'search'
			return s:get_gui_tab(l:vars.notmuch)
		elseif has_key(s:buf_num, 'thread') " notmuch-folder では notmuch-search と同じにするのを兼ねている
			return s:get_gui_tab(getbufinfo(s:buf_num.thread)[0].variables.notmuch)
		else
			return s:get_gui_tab(l:vars.notmuch)
		endif
	endif
endfunction

function s:get_gui_tab(vars) abort
	if has_key(a:vars, 'search_term')
		return '%N| notmuch [' .. a:vars.search_term .. ']%<'
	else  " notmuch-search 作成直後は b:notmuch.search_term 未定義
		return '%N| notmuch []%<'
	endif
endfunction

function s:set_title_etc() abort
	if &title && &titlestring ==# ''
		augroup NotmuchTitle
			autocmd!
			autocmd BufEnter,BufFilePost * let &titlestring=s:make_title()
		augroup END
	endif
	if has('gui_running') && &showtabline != 0 " && &guitablabel ==# ''
		set guitablabel=%!MakeGUITabline()
	endif
endfunction

function s:make_title() abort
	let l:tablist = tabpagenr('$')
	if l:tablist == 1
		let l:a = ''
	else
		let l:a = ' (' .. tabpagenr() .. ' of ' .. l:tablist .. ')'
	endif
	if &filetype =~# '^notmuch-'
		let l:title = 'Notmuch-Python-Vim'
	" elseif &filetype ==# 'notmuch-edit' " tabline を変えているので、こちらは変えない
	" ↓s:set_title_etc() の autocmd も次に書き換えが必要になる
	" autocmd BufEnter,BufFilePost,WinEnter * let &titlestring=s:make_title()
	" 	let l:title = '%{b:notmuch.subject} %{b:notmuch.date}%< %m ' .. '(' .. expand('%:~') .. ')'
	elseif &filetype ==# 'qf'
		let l:title = '%t'
	elseif &filetype ==# 'help'
		let l:title = '%h'
	elseif bufname('') ==# ''
		let l:title = '%t %m'
	else
		let l:title = '%t %m ' .. '(' .. expand('%:~:h') .. ')'
	endif
	return l:title .. l:a .. ' - ' .. v:servername
endfunction

function s:change_title() abort
	let l:type = py3eval('buf_kind()')
	if l:type ==# 'folders'
				\ || l:type ==# 'thread'
				\ || l:type ==# 'show'
				\ || l:type ==# 'edit'
				\ || l:type ==# 'draft'
				\ || l:type ==# 'search'
				\ || l:type ==# 'view'
		set titlestring=Notmuch-Python\ -\ Vim
	else
		set titlestring=%f%(\ %M%)%(\ (%{expand(\"%:p:h\")})%)%(\ %a%)
	endif
endfunction

function! s:search_not_notmuch() abort " notmuch-? 以外のリストされていて隠れていない、もしくは隠れていても更新されているバッファを探す
	let l:notmuch_kind = ['notmuch-folders', 'notmuch-thread', 'notmuch-show', 'notmuch-edit', 'notmuch-draft']
	let l:changed = 0
	for l:buf in getbufinfo()
		if count(l:notmuch_kind, getbufvar(l:buf.bufnr, '&filetype')) == 0
			if !l:buf.listed
				continue
			elseif l:buf.hidden
				if l:buf.changed
					let l:changed = l:buf.bufnr
				endif
			else
				return l:buf.bufnr
			endif
		endif
	endfor
	if l:changed
		return l:changed
	endif
	return 0
endfunction

function s:end_notmuch() abort " 全て終了 (notmuch-folders が bwipeout されたら呼ばれる)
	let l:bufinfo = getbufinfo()
	for l:buf in l:bufinfo
		let l:bufnr = l:buf.bufnr
		let l:ftype = getbufvar(l:bufnr, '&filetype')
		if l:ftype ==# 'notmuch-draft' && l:buf.changed || ( l:ftype ==# 'notmuch-edit' && l:buf.changed )
			call s:swich_buffer(l:bufnr)
			echohl WarningMsg | echo 'Editing ' .. l:ftype .. '.' | echohl None
			unlet s:buf_num.folders
			return
		endif
	endfor
	py3 make_dump()
	let l:bufnr = s:search_not_notmuch()
	if l:bufnr == 0
		cquit " →全終了
	endif
	call s:swich_buffer(l:bufnr)
	" notmuch-* バッファ削除
	let l:notmuch_kind = ['notmuch-folder', 'notmuch-thread', 'notmuch-show', 'notmuch-edit', 'notmuch-draft']
	for l:buf in l:bufinfo
		let l:bufnr = l:buf.bufnr
		if count(l:notmuch_kind, getbufvar(l:bufnr, '&filetype'))
			execute l:bufnr .. 'bwipeout'
		endif
	endfor
	call <SID>change_fold_highlight()
	unlet s:buf_num
endfunction

function s:swich_buffer(bufnr) abort " できるだけ指定されたバッファに切り替える
	" 他のタブページに有るか?
	let l:tabpage = 0
	for l:i in range(tabpagenr('$'))
		if match(tabpagebuflist(l:i + 1), a:bufnr) != -1
			let l:tabpage = l:i + 1
			break
		endif
	endfor
	if l:tabpage != 0 " タブページが有る場合
		execute l:tabpage .. 'tabnext'
	endif
	if win_gotoid(bufwinid(a:bufnr)) == 0
		let l:type = getbufvar(a:bufnr, '&filetype')
		if l:type ==# 'notmuch-edit' || l:type ==# 'notmuch-draft'
			let l:open_way = g:notmuch_open_way[strpart(l:type, 8)]
			if l:open_way ==# 'enew'
				execute 'silent buffer ' .. a:bufnr
			elseif l:open_way ==# 'tabedit'
				execute 'silent tab sbuffer ' .. a:bufnr
			else
				let l:open_way = substitute(l:open_way, '\<new\>',        'split',   '')
				let l:open_way = substitute(l:open_way, '\([0-9]\)new\>', '\1split', '')
				let l:open_way = substitute(l:open_way, '\<vnew\>',       'vsplit',  '')
				let l:open_way = substitute(l:open_way, '\([0-9]\)vnew\>','\1vsplit','')
				execute l:open_way
				execute 'silent buffer ' .. a:bufnr
			endif
		else
			execute a:bufnr .. 'buffer'
		endif
	endif
endfunction

function s:open_original(args) abort
	py3 do_mail(open_original, vim.eval('a:args'))
endfunction

function s:reload(args) abort
	let l:type = py3eval('buf_kind()')
	if l:type ==# 'show' || l:type ==# 'view'
		if !exists('b:notmuch.search_term') || !exists('b:notmuch.msg_id')
			return
		endif
		py3 reload_show()
		return
	endif
	if l:type ==# 'folders'
		if py3eval('is_same_tabpage("thread", "")')
			if getbufinfo(s:buf_num.thread)[0].variables.notmuch.search_term == g:notmuch_folders[line('.') - 1][1] " search_term が folder, thread で同じならリロード
				call win_gotoid(bufwinid(s:buf_num.thread))
				py3 reload_thread()
			else " search_term が folder, thread で異なるなら開く (同じ場合はできるだけ開いているメールを変えない)
				call s:open_thread(v:false, v:true)
			endif
		endif
	elseif l:type ==# 'thread' ||  l:type ==# 'search'
		py3 reload_thread()
	endif
endfunction

function s:get_tags() abort
	let l:tags = ''
	for l:t in py3eval('get_msg_tags_list("")')
		let l:tags = l:tags .. l:t .. ' '
	endfor
	return l:tags[:-1]
endfunction

function s:cursor_move_thread(search_term) abort
	if line('.') != line('v')
		return
	endif
	let l:type = py3eval('buf_kind()')
	if l:type ==# 'thread'
		let l:buf_num = s:buf_num.thread
	elseif l:type ==# 'search'
		let l:buf_num = s:buf_num.search[a:search_term]
	else
		return
	endif
	if bufnr('') != l:buf_num || py3eval('get_msg_id()') ==# '' || b:notmuch.msg_id == py3eval('get_msg_id()')
		return
	endif
	py3 change_buffer_vars()
	if py3eval('is_same_tabpage("show", "")') || py3eval('is_same_tabpage("view", ''' .. s:vim_escape(a:search_term) .. ''')')
		echo ''
		" ↑エラーなどのメッセージをクリア
		call s:open_mail()
	endif
endfunction

function s:new_mail(...) abort
	if !py3eval('"DBASE" in globals()')  " フォルダ一覧も非表示状態で呼ばれた場合
		call s:import()
		py3 set_subcmd_newmail()
		execute 'cd ' .. py3eval('get_save_dir()')
		if &title && &titlestring ==# ''
			let &titlestring=s:make_title()
		endif
		if has('gui_running') && &showtabline != 0 " && &guitablabel ==# ''
			set guitablabel=%!MakeGUITabline()
		endif
	endif
	py3 new_mail(vim.eval('a:000'))
endfunction

function s:forward_mail(args) abort
	py3 forward_mail()
endfunction

function s:forward_mail_attach(args) abort
	py3 forward_mail_attach()
endfunction

function s:forward_mail_resent(args) abort
		py3 forward_mail_resent()
endfunction

function s:reply_mail(args) abort
	py3 reply_mail()
endfunction

function s:send_vim(args) abort
	py3 send_vim()
endfunction

function s:save_mail(args) abort
	let l:winid = bufwinid(bufnr(''))
	let l:type = py3eval('buf_kind()')
	if l:type ==# 'folders' || l:type ==# 'thread'
		if !win_gotoid(bufwinid(s:buf_num.show))
			return
		endif
	elseif l:type ==# 'search'
		if !win_gotoid(bufwinid(s:buf_num.view[b:notmuch.search_term]))
			return
		endif
	endif
	let l:save_file = py3eval('get_save_filename(get_save_dir())')
	if l:save_file ==# ''
		echo "\n"
		echo 'No save.'
		return
	endif
	redraw
	setlocal modifiable
	execute 'write! ' .. l:save_file
	setlocal nomodifiable
	call win_gotoid(l:winid)
endfunction

function s:move_mail(args) abort
	py3 do_mail(move_mail, vim.eval('a:args'))
endfunction

function notmuch_py#comp_dir(ArgLead, CmdLine, CursorPos) abort
	let l:folders = py3eval('get_mail_folders()')
	let l:filter_cmd = printf('v:val =~ "^%s"', a:ArgLead)
	return filter(l:folders, l:filter_cmd)
endfunction

function s:run_shell_program(args) abort
	py3 do_mail(run_shell_program, vim.eval('a:args'))
endfunction

function s:reindex_mail(args) abort
	py3 do_mail(reindex_mail, vim.eval('a:args'))
endfunction

function s:import_mail(args) abort
	py3 import_mail(vim.eval('a:args'))
endfunction

function s:delete_mail(args) abort
	py3 do_mail(delete_mail, vim.eval('a:args'))
endfunction

function s:export_mail(args) abort
	py3 do_mail(export_mail, vim.eval('a:args'))
endfunction

function s:delete_attachment(args) abort
	py3 delete_attachment(vim.eval('a:args'))
endfunction

function s:close(args) abort " notmuch-* を閉じる (基本 close なので隠すだけ) が、他のバッファが残っていれば Vim を終了させずに、そのバッファを復活させる
	if winnr('$') == 1 && tabpagenr('$') == 1
		let l:bufnr = s:search_not_notmuch()
		if l:bufnr
			execute l:bufnr .. 'buffer'
		else
			quit
		endif
	else
		close
	endif
endfunction

function s:augroup_notmuch_select(win, reload) abort " notmuch-edit 閉じた時の処理(呼び出し元に戻り notmuch-show が同じタブページに有れば再読込)
	let l:bufnr = bufnr()
	execute 'augroup NotmuchEdit' .. l:bufnr
		autocmd!
		execute 'autocmd BufWinLeave <buffer> call s:change_exist_tabpage_core(' .. a:win .. ') |' ..
					\ '    if py3eval(''is_same_tabpage("show", "")'') |' ..
					\ '      if ' .. a:reload .. ' |'
					\ '        call win_gotoid(bufwinid(s:buf_num["show"])) |' ..
					\ '        call s:reload([]) |' ..
					\ '      endif |'
					\ '      call win_gotoid(bufwinid(' .. a:win .. ')) |' ..
					\ '      autocmd! NotmuchEdit' .. l:bufnr .. ' |' ..
					\ '    endif'
	augroup END
	" a:win に戻れない時は、そのバッファを読み込みたいが以下の方法でも駄目
					" \ '    if win_gotoid(bufwinid(' .. a:win .. ')) == 0 |' ..
					" \ '      buffer ' .. a:win .. '|' ..
					" \ '    endif | ' ..
endfunction

function s:au_new_mail() abort " 新規/添付転送メールでファイル末尾移動時に From 設定や署名の挿入
	let l:bufnr = bufnr()
	execute 'augroup NotmuchNewAfter' .. l:bufnr
		autocmd!
		execute 'autocmd CursorMoved,CursorMovedI <buffer> py3 set_new_after(' .. l:bufnr .. ')'
	augroup END
endfunction

function s:au_reply_mail() abort " 返信メールでファイル末尾移動時に From 設定や署名・返信元引用文の挿入
	let l:bufnr = bufnr()
	execute 'augroup NotmuchReplyAfter' .. l:bufnr
		autocmd!
		execute 'autocmd CursorMoved,CursorMovedI <buffer> py3 set_reply_after(' .. l:bufnr .. ')'
	augroup END
endfunction

function s:au_forward_mail() abort " 転送メールでファイル末尾移動時に From 設定や署名・転送元の挿入
	let l:bufnr = bufnr()
	execute 'augroup NotmuchForwardAfter' .. l:bufnr
		autocmd!
		execute 'autocmd CursorMoved,CursorMovedI <buffer> py3 set_forward_after(' .. l:bufnr .. ')'
	augroup END
endfunction

function s:au_resent_mail() abort " 転送メールでファイル末尾移動時に From 設定や署名・転送元の挿入
	let l:bufnr = bufnr()
	execute 'augroup NotmuchResentAfter' .. l:bufnr
		autocmd!
		execute 'autocmd CursorMoved,CursorMovedI <buffer> py3 set_resent_after(' .. l:bufnr .. ')'
	augroup END
endfunction

function s:au_write_draft() abort " draft mail の保存
	let l:bufnr = bufnr()
	execute 'augroup NotmuchSaveDraft' .. l:bufnr
		autocmd!
		execute 'autocmd BufWritePost <buffer> py3 save_draft()'
		execute 'autocmd BufWipeout <buffer> autocmd! NotmuchSaveDraft' .. l:bufnr
	augroup END
endfunction

function s:close_boundary(header_end, close_start, boundary_start) abort " ヘッダの最後から multipart 部まで纏めて折りたたむ
	let l:i = a:boundary_start
	while v:true
		for l:str in getline(l:i, '$')
			let l:boundary = matchstr(l:str, '\m\c\%(\<boundary=["'']\)\@<=[^"'']\+')
			if l:boundary !=? ''
				break
			endif
			let l:i += 1
		endfor
		let l:boundary = '^--' .. l:boundary .. '$'
		for l:str in getline(l:i, '$')
			if match(l:str, l:boundary) != -1
				break
			endif
			let l:i += 1
		endfor
		for l:str in getline(l:i, '$')
			if match(l:str, '^Content-Type: \?multipart\/\c') != -1
				call s:close_boundary(a:header_end, a:close_start, l:i)
				return
			elseif l:str ==# ''
				let l:i -= 1
				execute printf('%d', a:header_end + 1) .. ',' printf('%d', l:i) .. 'fold'
				execute printf('%d', a:close_start) .. ',' .. printf('%d', l:i) .. 'fold'
				return
			endif
			let l:i += 1
		endfor
		break
	endwhile
endfunction

function s:fold_open() abort " 折畳全開を試み、無くてもエラーとしない
	try
		normal! zO
		py3 reset_cursor_position(vim.current.buffer, vim.current.window, vim.current.window.cursor[0])
	catch /^Vim\%((\a\+)\)\=:E490:/
		" 何もしない
	endtry
endfunction

function s:mark_in_thread(args) range abort
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
		call s:fold_open()
		normal! j
		call s:fold_open()
	endif
endfunction

function s:cut_thread(args) abort
	py3 cut_thread(get_msg_id(), [])
endfunction

function s:connect_thread(args) abort
	py3 connect_thread_tree()
endfunction

function s:command_marked(args) abort " マークしたメールに纏めてコマンド実行
	call remove(a:args, 0, 1)
	py3 command_marked(vim.eval('a:args'))
endfunction

function notmuch_py#comp_all_args(ArgLead, CmdLine, CursorPos) abort
	let l:cmdline = substitute(a:CmdLine, '[\n\r]\+', ' ', 'g')
	let l:last = py3eval('get_last_cmd(get_cmd_name(), "' .. l:cmdline .. '", ' .. a:CursorPos .. ')')
	if l:last == []
		let l:snippet = py3eval('get_cmd_name_ftype()')
	else
		let l:cmd = l:last[0]
		" let l:cmds = py3eval('get_command()')
		if and(g:notmuch_command[l:cmd][1], 0x01) == 0
			return []
		else
			if match(a:CmdLine, 'Notmuch \+mark-command *') != -1
				let l:match = matchend(a:CmdLine, '\m\CNotmuch \+mark-command *')
				return s:complete_command(strpart(a:CmdLine, l:match), a:CursorPos - l:match, v:true)
			elseif l:cmd ==# 'run'
				let l:snippet = py3eval('get_sys_command(''' .. s:vim_escape(a:CmdLine) .. ''' , ''' .. s:vim_escape(a:ArgLead) .. ''')')
			elseif l:cmd ==# 'mail-move' || l:cmd ==# 'set-fcc'
				if l:last[1] " 既に引数が有る
					return []
				endif
				let l:snippet = py3eval('get_mail_folders()')
			elseif l:cmd ==# 'tag-add'
				return s:complete_tag_common('get_msg_tags_diff', a:CmdLine, a:CursorPos, v:true)
			elseif l:cmd ==# 'tag-delete'
				return s:complete_tag_common('get_msg_tags_list', a:CmdLine, a:CursorPos, v:true)
			elseif l:cmd ==# 'tag-set'
				return s:complete_tag_common('get_msg_tags_any_kind', a:CmdLine, a:CursorPos, v:true)
			elseif l:cmd ==# 'tag-toggle'
				return s:complete_tag_common('get_msg_all_tags_list', a:CmdLine, a:CursorPos, v:true)
			elseif l:cmd ==# 'search' || l:cmd ==# 'search-refine'
				let l:snippet = s:get_snippet('get_search_snippet', a:CmdLine, a:CursorPos, v:true)
				return s:is_one_snippet(l:snippet)
			elseif l:cmd ==# 'thread-sort'
				let l:snippet = s:get_sort_snippet(a:CmdLine, a:CursorPos, v:true)
				return s:is_one_snippet(l:snippet)
			elseif l:cmd ==# 'set-encrypt'
				let l:snippet = ['Encrypt', 'Signature', 'S/MIME', 'PGP/MIME', 'PGP', 'Subject', 'Public-Key']
			elseif l:cmd ==# 'set-attach' || l:cmd ==# 'mail-import'
				let l:dir = substitute(a:CmdLine, '^Notmuch\s\+' .. l:cmd .. '\s\+', '', '')
				if l:dir ==# ''
					let l:snippet = glob(py3eval('os.path.expandvars(''$USERPROFILE\\'') if os.name == ''nt'' else os.path.expandvars(''$HOME/'')') .. '*', 1, 1)
				else
					if isdirectory(l:dir)
						let l:dir = l:dir .. '/*'
					else
						let l:dir =  l:dir .. '*'
					endif
					let l:snippet = glob(l:dir, 1, 1)
				endif
				if len(l:snippet) == 1
					if isdirectory(l:snippet[0])
						let l:snippet = glob(l:dir .. '/*', 1, 1)
					endif
				endif
			endif
		endif
	endif
	let l:filter_cmd = printf('v:val =~ "^%s"', a:ArgLead)
	let l:snippet = filter(l:snippet, l:filter_cmd)
	if len(l:snippet) == 0
		return []
	elseif len(l:snippet) == 1
		return [ l:snippet[0] .. ' ' ]
	else
		return l:snippet
	endif
endfunction

function notmuch_py#comp_cmd(ArgLead, CmdLine, CursorPos) abort
	return s:complete_command(a:CmdLine, a:CursorPos, 0)
endfunction

function s:complete_command(CmdLine, CursorPos, direct_command) abort
	let l:cmdLine = split(a:CmdLine[0:a:CursorPos-1], ' ')
	if a:CmdLine[a:CursorPos-1] ==# ' '
		let l:filter = ''
		let l:prefix = join(l:cmdLine, ' ')
	elseif a:CmdLine !=? ''
		let l:filter = l:cmdLine[-1]
		let l:prefix = join(l:cmdLine[0:-2], ' ')
	else
		let l:filter = ''
		let l:prefix = ''
	endif
	if l:prefix !=?  ''
		let l:prefix = l:prefix .. ' '
	endif
	let l:cmdline = substitute(a:CmdLine, '[\n\r]\+', ' ', 'g')
	let l:pos = a:CursorPos + 1
	let l:last = py3eval('get_last_cmd(get_mark_cmd_name(), " ' .. l:cmdline .. '", ' .. l:pos .. ')')
	if l:last == []
		let l:list = py3eval('get_mark_cmd_name()')
	else
		let l:cmd = l:last[0]
		let l:cmds = py3eval('get_command()')
		if l:cmd ==# 'mail-move'
			if l:last[1] " 既に引数が有る
				let l:list = py3eval('get_mark_cmd_name()')
			else
				let l:list = py3eval('get_mail_folders()')
			endif
		elseif l:cmd ==# 'run' " -complete=shellcmd 相当のことがしたいけどやり方不明
			" let l:list = []
			return []
		elseif l:cmds[l:cmd][0] ==# '0' " 引数を必要としないコマンド→次のコマンドを補完対象
			let l:list = py3eval('get_mark_cmd_name()')
		else
			if l:last[1]
				let l:list = extend(py3eval('get_msg_all_tags_list("")'), py3eval('get_mark_cmd_name()'))
			else
				let l:list = py3eval('get_msg_all_tags_list("")')
			endif
		endif
	endif
	let l:filter = printf('v:val =~ "^%s"', l:filter)
	let l:snippet_org = filter(l:list, l:filter)
	if a:direct_command  " input() 関数ではなく、command 直接の補完
		if len(l:snippet_org) == 1
			return [ l:snippet_org[0] .. ' ' ]
		endif
			return l:snippet_org
	endif
	" 補完候補にカーソル前の文字列を追加
	let l:snippet = []
	for l:v in l:snippet_org
		call add(l:snippet, l:prefix .. l:v)
	endfor
	if len(l:snippet) == 1
		return [ l:snippet[0] .. ' ' ]
	endif
	return l:snippet
endfunction

function s:notmuch_search(args) abort " notmuch search
	py3 notmuch_search(vim.eval('a:args'))
endfunction

function s:notmuch_thread(args) abort
	py3 notmuch_thread()
endfunction

function s:notmuch_address(args) abort
	py3 notmuch_address()
endfunction

function s:notmuch_duplication(args) abort
	py3 notmuch_duplication(0)
endfunction

function notmuch_py#comp_search(ArgLead, CmdLine, CursorPos) abort
	let l:snippet = s:get_snippet('get_search_snippet', a:CmdLine, a:CursorPos, v:false)
	return s:is_one_snippet(l:snippet)
endfunction

function notmuch_py#comp_run(ArgLead, CmdLine, CursorPos) abort
	let l:cmdLine = split(a:CmdLine[0:a:CursorPos-1], ' ')
	if a:CmdLine[a:CursorPos-1] ==# ' '
		let l:filter = ''
		let l:prefix = join(l:cmdLine, ' ')
	elseif a:CmdLine !=? ''
		let l:filter = l:cmdLine[-1]
		let l:prefix = join(l:cmdLine[0:-2], ' ')
	else
		let l:filter = ''
		let l:prefix = ''
	endif
	if l:prefix !=?  ''
		let l:prefix = l:prefix .. ' '
	endif
	let l:list =  py3eval('get_sys_command(''' .. s:vim_escape('Notmuch run ' .. a:CmdLine) .. ''' , ''' .. s:vim_escape(l:filter) .. ''')')
	let l:filter = printf('v:val =~ "^%s"', l:filter)
	let l:snippet_org = filter(l:list, l:filter)
	" 補完候補にカーソル前の文字列を追加
	let l:snippet = []
	for l:v in l:snippet_org
		call add(l:snippet, l:prefix .. l:v)
	endfor
	return l:snippet
" endfunction
	" return s:is_one_snippet(l:snippet)
endfunction

function s:is_one_snippet(snippet) abort  " 補完候補が 1 つの場合を分ける
	if len(a:snippet) != 1
		return a:snippet
	endif
	let l:snippet = a:snippet[0]
	if l:snippet[len(l:snippet)-1] ==# ':'
		return [l:snippet]
	else
		return [ l:snippet .. ' ' ]
	endif
endfunction

function s:toggle_thread(args) abort
	let l:seletc_thread = line('.')
	if foldclosed(l:seletc_thread) == -1
		let s:seletc_thread = line('.')
		normal! zC
		if foldclosed(l:seletc_thread) != -1  " 直前で再帰的に閉じたのに -1 なら単一メールのスレッド
			call cursor(foldclosed(s:seletc_thread), 1)
		endif
	else
		if exists('s:seletc_thread')
			if s:seletc_thread <= foldclosedend(l:seletc_thread) && s:seletc_thread >= foldclosed(l:seletc_thread)
				py3 reset_cursor_position(vim.current.buffer, vim.current.window, vim.bindeval('s:seletc_thread'))
			else
				py3 reset_cursor_position(vim.current.buffer, vim.current.window, vim.bindeval('foldclosedend(l:seletc_thread)'))
			endif
		endif
		normal! zO
		py3 reset_cursor_position(vim.current.buffer, vim.current.window, vim.current.window.cursor[0]) # zO の前だけだと、カーソル上下移動で桁位置が先頭になる
	endif
endfunction

function s:thread_change_sort(args) abort
	py3 thread_change_sort(vim.eval('a:args'))
endfunction

function s:set_fcc(s) abort
	py3 set_fcc(vim.eval('a:s'))
endfunction

function s:set_attach(s) abort
	py3 set_attach(vim.eval('a:s'))
endfunction

function s:set_encrypt(s) abort
	py3 set_encrypt(vim.eval('a:s'))
endfunction

function s:is_sametab_thread() abort
	let l:type = py3eval('buf_kind()')
	if l:type ==# 'thread' || l:type ==# 'search'
		return v:true
	elseif l:type ==# 'folders' ||
				\ l:type ==# 'show' ||
				\ l:type ==# 'view'
		for l:b in tabpagebuflist()
			if l:b == get(s:buf_num, 'thread', 0)
				return v:true
			endif
			for l:s in values(get(s:buf_num, 'search', {}))
				if l:b == l:s
					return v:true
				endif
			endfor
		endfor
		return v:false
	endif
	return v:false
endfunction

function s:notmuch_refine(s) abort
	py3 notmuch_refine(vim.eval('a:s'))
endfunction

function s:notmuch_down_refine(dummy) abort
	py3 notmuch_down_refine()
endfunction

function s:notmuch_up_refine(dummy) abort
	py3 notmuch_up_refine()
endfunction

function notmuch_py#get_highlight(hi) abort
	return substitute(substitute(substitute(execute('highlight ' .. a:hi),
				\ '[\n\r \t]\+', ' ', 'g'),
				\ ' *' .. a:hi .. '\s\+xxx *', '', ''),
				\ '\(font=\(\w\+ \)\+\ze\w\+=\|font=\(\w\+ \?\)\+$\)', '', '')
endfunction

let s:fold_highlight = notmuch_py#get_highlight('Folded')
let s:specialkey_highlight = notmuch_py#get_highlight('SpecialKey')
if exists('g:notmuch_visible_line') && g:notmuch_visible_line !=# '' && g:notmuch_visible_line != 1 && g:notmuch_visible_line != 2
	try
		let s:normal_highlight = execute('highlight ' .. g:notmuch_visible_line)
		let s:normal_highlight = notmuch_py#get_highlight(g:notmuch_visible_line)
	catch /^Vim\%((\a\+)\)\=:E411:/
		augroup notmuch_visible_line
			autocmd!
			autocmd BufEnter * echohl WarningMsg | echomsg 'E411: highlight group not found: ' .. g:notmuch_visible_line | echomsg 'Error setting: g:notmuch_visible_line' | echohl None | autocmd! notmuch_visible_line
		augroup END
		let s:normal_highlight = ''
	endtry
else
	let s:normal_highlight = ''
endif
function s:change_fold_highlight() abort " Folded の色変更↑highlight の保存
	if s:is_sametab_thread()
		highlight Folded NONE
		if s:normal_highlight !=# ''
			highlight SpecialKey NONE
			execute 'silent! highlight SpecialKey ' .. s:normal_highlight
		endif
	else
		execute 'silent! highlight Folded ' .. s:fold_highlight
		if s:normal_highlight !=# ''
			execute 'silent! highlight SpecialKey ' .. s:specialkey_highlight
		endif
	endif
endfunction

function s:is_gtk() abort
	if !has('gui_running')
		return 0
	endif
	let l:gtk = execute('version')
	if match(l:gtk, '\<with GTK\d\? GUI\.') != -1
		return 1
	endif
		return 0
endfunction

augroup ChangeFoldHighlight
	autocmd!
	autocmd BufEnter,WinEnter * call <SID>change_fold_highlight()
augroup END

augroup NotmuchFileType
	autocmd!
	autocmd FileType notmuch-edit setlocal syntax=notmuch-draft
	" ↑syntax の反映が setlocal filetype=xxx に引きずられる
augroup END

function FoldThreadText() abort
	return py3eval('get_folded_list(' .. v:foldstart .. ',' .. v:foldend .. ')')
endfunction

function FoldThread(n) abort " スレッド・リストの折畳設定
	" a:n Subject が何番目に表示されるのか?
	" strpart() を使った方法は 全角=2 バイトとは限らないので駄目
	let l:str = getline(v:lnum)
	if a:n == 0
		let l:str = substitute(l:str, '^[^\t]\+\t  ', '', 'g')
	elseif a:n == 1
		let l:str = substitute(l:str, '^[^\t]\+\t[^\t]\+\t  ', '', 'g')
	elseif a:n == 2
		let l:str = substitute(l:str, '^[^\t]\+\t[^\t]\+\t[^\t]\+\t  ', '', 'g')
	endif
	let l:depth = strlen(matchstr(l:str, '\m^ \+')) / 2
	if l:depth
		return l:depth + 1
	else
		return '>1'
	endif
endfunction

function FoldHeaderText() abort " メールでは foldtext を変更する
	for l:line in getline(v:foldstart, '$')
		if substitute(l:line, '^[ \t]\+$', '','') !=? ''
			break
		endif
	endfor
	let cnt = printf('[%' .. len(line('$')) .. 's] ', (v:foldend - v:foldstart + 1))
	let line_width = winwidth(0) - &foldcolumn

	if &number
		let line_width -= max([&numberwidth, len(line('$'))])
	" sing の表示非表示でずれる分の補正
	elseif &signcolumn ==# 'number'
		let cnt = cnt .. '  '
	endif
	if &signcolumn ==# 'auto'
		let cnt = cnt .. '  '
	endif
	let line_width -= 2 * (&signcolumn ==# 'yes')

	let l:line = substitute(l:line, '^[\x0C]', '','')
	let l:line = strcharpart(printf('%s', l:line), 0, l:line_width-len(cnt))
	" 全角文字を使っていると、幅でカットすると広すぎる
	" だからといって strcharpart() の代わりに strpart() を使うと、逆に余分にカットするケースが出てくる
	" ↓末尾を 1 文字づつカットしていく
	while strdisplaywidth(l:line) > l:line_width-len(cnt)
		let l:line = slice(l:line, 0, -1)
	endwhile
	return printf('%s%' .. (l:line_width-strdisplaywidth(l:line)) .. 'S', l:line, cnt)
endfunction
