" Author:  Iranoan <iranoan+vim@gmail.com>
" License: GPL Ver.3.

scriptencoding utf-8
scriptversion 4

if exists('b:did_ftplugin_plugin')
	finish
endif
let b:did_ftplugin_plugin = 1

" if !exists('g:ft_notmuch_draft')
" 	let g:ft_notmuch_draft = 1
" endif

execute 'source ' .. expand('<sfile>:p:h:h') .. '/macros/notmuch-edit.vim'
setlocal signcolumn=auto foldmethod=syntax
if &foldcolumn == 0
	setlocal foldcolumn=1
endif

" keymap
nnoremap <buffer><silent><Leader>s :Notmuch mail-send<CR>
nnoremap <buffer><silent><leader>a :Notmuch tag-add<CR>
nnoremap <buffer><silent><leader>t :Notmuch tag-toggle<CR>
nnoremap <buffer><silent><leader>A :Notmuch tag-delete<CR>
nnoremap <buffer><silent><leader>d :Notmuch tag-delete<CR>
nnoremap <buffer><silent><leader>p :Notmuch mail-info<CR>
nnoremap <buffer><silent><leader>f :Notmuch set-fcc<CR>
nnoremap <buffer><silent><leader>c :Notmuch set-attach<CR>
nnoremap <buffer><silent><leader>e :Notmuch set-encrypt<CR>
nnoremap <buffer><silent><leader>h :topleft help notmuch-python-vim-draft-keymap<CR>
nnoremap <buffer><silent><F1>      :topleft help notmuch-python-vim-draft-keymap<CR>
