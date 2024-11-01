vim9script
# Author:  Iranoan <iranoan+vim@gmail.com>
# License: GPL Ver.3.

scriptencoding utf-8

if exists('b:did_ftplugin_plugin')
	finish
endif
b:did_ftplugin_plugin = 1

setlocal statusline=%<%{b:notmuch.unread_mail}/%{b:notmuch.all_mail}\ [%{b:notmuch.flag_mail}]\ %=%4l/%L
setlocal cursorline nowrap winminwidth=20 nolist signcolumn=auto nonumber foldcolumn=0

# keymap
nnoremap <buffer><silent>o     :Notmuch open<CR>
nnoremap <buffer><2-LeftMouse> :Notmuch open<CR>
nnoremap <buffer><silent>s     :Notmuch search<CR>

if exists('b:undo_ftplugin')
	b:undo_ftplugin ..= '| call undoftplgin#Folder()'
else
	b:undo_ftplugin = 'call undoftplgin#Folder()'
endif

