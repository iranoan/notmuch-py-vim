" Author:  Iranoan <iranoan+vim@gmail.com>
" License: GPL Ver.3.

scriptencoding utf-8

" キーマップのみ
nnoremap <buffer><silent><Leader>s :Notmuch mail-send<CR>
nnoremap <buffer><silent><leader>a :Notmuch tag-add<CR>
nnoremap <buffer><silent><leader>t :Notmuch tag-toggle<CR>
nnoremap <buffer><silent><leader>d :Notmuch tag-delete<CR>
nnoremap <buffer><silent><leader>q :bwipeout!<CR>
