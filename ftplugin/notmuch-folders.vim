" Author:  Iranoan <iranoan+vim@gmail.com>
" License: GPL Ver.3.

scriptencoding utf-8

if exists('b:did_ftplugin_user')
	finish
endif
let b:did_ftplugin_user = 1

" if !exists('g:ft_notmuch_folders')
" 	let g:ft_notmuch_folders = 1
" endif

setlocal statusline=%<%{b:notmuch.unread_mail}/%{b:notmuch.all_mail}\ [%{b:notmuch.flag_mail}]\ %=%4l/%L
setlocal cursorline nowrap winminwidth=20 nolist signcolumn=auto nonumber foldcolumn=0 nolist

" keymap
nnoremap <buffer><silent>o :Notmuch open<CR>
nnoremap <2-LeftMouse>     :Notmuch open<CR>
nnoremap <buffer><silent>s :Notmuch search<CR>
