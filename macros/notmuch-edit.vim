vim9script
# Author:  Iranoan <iranoan+vim@gmail.com>
# License: GPL Ver.3.
scriptencoding utf-8
# notmuch-edit, notmuch-draft の共通要素

setlocal expandtab autoindent nosmartindent nocindent indentexpr=
setlocal formatoptions+=ql comments=n:>
setlocal foldtext=notmuch_py#FoldHeaderText()

# keymap
nnoremap <buffer><silent><leader>q : if len(getbufinfo()) == 1 \| quit!  \|else \| bwipeout!  \|endif<CR>

b:undo_ftplugin ..= '| call undoftplgin#EditDraft()'
