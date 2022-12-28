" Author:  Iranoan <iranoan+vim@gmail.com>
" License: GPL Ver.3.

scriptencoding utf-8
scriptversion 4

if exists('b:did_ftplugin_user')
	finish
endif
let b:did_ftplugin_user = 1

if !exists('g:ft_notmuch_thread')
	let g:ft_notmuch_thread = 1
	augroup NotmuchThreadType
		autocmd!
		if has('patch-8.2.2518')
			autocmd BufWinEnter,WinNew * if &filetype ==# 'notmuch-thread' | setlocal list foldlevel=0 | endif
		else
			autocmd BufWinEnter,WinNew * if &filetype ==# 'notmuch-thread' | setlocal nolist foldlevel=0 | endif
		endif
	augroup END
endif

function s:set_colorcolmun() abort
	let l:colorcolumn = 7
	let l:n_colorcolumn = 7
	for l:i in split(py3eval('notmuchVim.subcommand.DISPLAY_FORMAT2'), '[{}\t]\+')[0 : 1]
		if l:i == '0'
			let l:n_colorcolumn += py3eval('notmuchVim.subcommand.SUBJECT_LENGTH') + 1
			let l:colorcolumn ..= ',' .. l:n_colorcolumn
		elseif l:i == '1'
			let l:n_colorcolumn += py3eval('notmuchVim.subcommand.FROM_LENGTH') + 1
			let l:colorcolumn ..= ',' .. l:n_colorcolumn
		elseif l:i == '2'
			let l:n_colorcolumn += py3eval('notmuchVim.subcommand.TIME_LENGTH') + 1
			let l:colorcolumn ..= ',' .. l:n_colorcolumn
		endif
	endfor
	execute 'setlocal colorcolumn=' .. l:colorcolumn
	if g:notmuch_visible_line == 2
		execute 'highlight ColorColumn ' .. substitute(notmuch_py#get_highlight('Normal'), '\m\C\%(bg\|fg\)\ze\=', '\={"bg": "fg", "fg": "bg"}[submatch(0)]', 'g')
	endif
endfunction

setlocal statusline=%<%{(line('$')==1&&getline('$')==#'')?'\ \ \ -/-\ \ \ ':printf('%4d/%-4d',line('.'),line('$'))}\ tag:\ %{b:notmuch.tags}%=%4{line('w$')*100/line('$')}%%
sign define notmuch text=* texthl=notmuchMark
if exists('g:notmuch_visible_line') && ( g:notmuch_visible_line == 1 || g:notmuch_visible_line == 2 )
	setlocal nomodifiable tabstop=1 cursorline nowrap nonumber signcolumn=yes foldmethod=expr foldminlines=1 foldcolumn=0 foldtext=FoldThreadText() foldlevel=0 concealcursor=nv conceallevel=3 nolist
	call s:set_colorcolmun()
elseif has('patch-8.2.2518')
	setlocal nomodifiable tabstop=1 cursorline nowrap nonumber signcolumn=yes foldmethod=expr foldminlines=1 foldcolumn=0 foldtext=FoldThreadText() foldlevel=0 concealcursor=nv conceallevel=3 list listchars=tab:\|,
else
	setlocal nomodifiable tabstop=1 cursorline nowrap nonumber signcolumn=yes foldmethod=expr foldminlines=1 foldcolumn=0 foldtext=FoldThreadText() foldlevel=0 concealcursor=nv conceallevel=3 nolist
endif
if exists('g:notmuch_display_item')
	execute 'setlocal foldexpr=FoldThread(' .. index(g:notmuch_display_item, 'Subject', 0, v:true) .. ')'
else
	setlocal foldexpr=FoldThread(0)
endif

" keymap
nnoremap <buffer><silent>a :Notmuch tag-add<CR>
vnoremap <buffer><silent>a :Notmuch tag-add<CR>
nnoremap <buffer><silent>A :Notmuch tag-delete<CR>
vnoremap <buffer><silent>A :Notmuch tag-delete<CR>
nnoremap <buffer><silent>C :Notmuch thread-connect<CR>
nnoremap <buffer><silent>d :Notmuch tag-set +Trash -unread<CR>:normal! jzO<CR>
vnoremap <buffer><silent>d :Notmuch tag-set +Trash -unread<CR>:normal! `>0jzO<CR>
nnoremap <buffer><silent>D :Notmuch attach-delete<CR>
vnoremap <buffer><silent>D :Notmuch attach-delete<CR>
nnoremap <buffer><silent>o :Notmuch thread-toggle<CR>
nnoremap <buffer><silent>O :Notmuch open<CR>
nnoremap <buffer><silent>s :Notmuch search<CR>
nnoremap <buffer><silent>S :Notmuch mail-save<CR>
nnoremap <buffer><silent>u :Notmuch tag-toggle unread<CR>:normal! jzO<CR>
vnoremap <buffer><silent>u :Notmuch tag-toggle unread<CR>:normal! `>0jzO<CR>
nnoremap <buffer><silent>zn <Nop>
