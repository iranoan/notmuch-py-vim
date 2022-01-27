" Author:  Iranoan <iranoan+vim@gmail.com>
" License: GPL Ver.3.

scriptencoding utf-8

if exists('b:did_ftplugin_user')
	finish
endif
let b:did_ftplugin_user = 1

if !exists('g:ft_notmuch_thread')
	let g:ft_notmuch_thread = 1
	augroup NotmuchThreadType
		autocmd!
		autocmd BufWinEnter,WinNew * if &filetype ==# 'notmuch-thread' |
					\ if has('patch-8.2.2518') |
					\		setlocal list foldlevel=0 |
					\ else |
					\		setlocal nolist foldlevel=0 |
					\ endif |
					\ endif
	augroup END
endif

setlocal statusline=%<%{(line('$')==1&&getline('$')==#'')?'\ \ \ -/-\ \ \ ':printf('%4d/%-4d',line('.'),line('$'))}\ tag:\ %{b:notmuch.tags}%=%4{line('w$')*100/line('$')}%%
sign define notmuch text=* texthl=notmuchMark
if has('patch-8.2.2518')
	setlocal nomodifiable tabstop=1 cursorline nowrap nolist nonumber signcolumn=yes foldmethod=expr foldminlines=1 foldcolumn=0 foldtext=FoldThreadText() list foldlevel=0 listchars=tab:\|,
else
	setlocal nomodifiable tabstop=1 cursorline nowrap nolist nonumber signcolumn=yes foldmethod=expr foldminlines=1 foldcolumn=0 foldtext=FoldThreadText() nolist foldlevel=0
endif
if exists('g:notmuch_display_item')
	execute 'setlocal foldexpr=FoldThread(' . index(g:notmuch_display_item, 'Subject', 0, v:true) . ')'
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
