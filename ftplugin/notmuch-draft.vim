" Author:  Iranoan <iranoan+vim@gmail.com>
" License: GPL Ver.3.

scriptencoding utf-8

" キーマップのみ
nnoremap <buffer><silent><Leader>s :Notmuch mail-send<CR>
nnoremap <buffer><silent><leader>a :Notmuch tag-add<CR>
nnoremap <buffer><silent><leader>t :Notmuch tag-toggle<CR>
nnoremap <buffer><silent><leader>A :Notmuch tag-delete<CR>
nnoremap <buffer><silent><leader>d :Notmuch tag-delete<CR>
nnoremap <buffer><silent><leader>p :Notmuch mail-info<CR>
nnoremap <buffer><silent><leader>f :Notmuch set-fcc<CR>
nnoremap <buffer><silent><leader>c :Notmuch set-attach<CR>
nnoremap <buffer><silent><leader>e :Notmuch set-encrypt<CR>
nnoremap <buffer><silent><leader>q :bwipeout!<CR>
nnoremap <buffer><silent><leader>h :topleft help notmuch-python-vim-draft-keymap<CR>
nnoremap <buffer><silent><F1>      :topleft help notmuch-python-vim-draft-keymap<CR>
