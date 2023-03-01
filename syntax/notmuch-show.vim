" Vim syntax file
" Language: notmuch-show window
scriptversion 4

" Quit when a syntax file was already loaded
if exists('b:current_syntax')
	finish
endif

let s:cpo_save = &cpoptions
set cpoptions&vim

syntax case ignore

syntax match   mailNewPartHead  contained contains=@NoSpell '^[\x0C]\zs.\+ part$'
syntax region  mailHeader       contained contains=mailNewPartHead,@mailHeaderFields,@NoSpell start='^[\x0C].\+ part$' skip='^\s' end='^[^:]*\n' fold
syntax region  mailNewPart      contains=mailHeader,@markdownBlock,@mailHeaderFields,@NoSpell start='^[\x0C].\+ part$' end='^[\x0C]'me=e-1 fold
syntax region  mailNewPart      contains=mailNewPartHead,@markdownBlock,@mailHeaderFields,@NoSpell start='^[\x0C]HTML part$' end='^[\x0C]'me=e-1 fold

" Usenet headers
syntax match   mailHeaderKey    contained contains=mailHeaderEmail,mailEmail,@NoSpell /\v^[a-z-]+:\s*/
syntax region mailHeader                 contains=mailHideHeader,@mailHeaderFields,@NoSpell start='\%^' skip='^\s' end='^$'me=s-1 fold

execute 'source ' .. expand('<sfile>:p:h:h') .. '/macros/syntax-common.vim'

 " marddown
syntax cluster markdownInline contains=markdownLinkText,markdownItalic,markdownBold
syntax cluster markdownBlock contains=markdownH1,markdownH2,markdownH3,markdownH4,markdownH5,markdownH6
syntax region markdownItalic matchgroup=markdownItalicDelimiter start=" _\S\@=" end="\S\@<=_ " skip="\\_" contains=markdownLineStart,@Spell,markdownLink,markdownLinkText concealends oneline
syntax region markdownBold matchgroup=markdownBoldDelimiter start="\*\*\S\@=" end="\S\@<=\*\*" skip="\\\*" contains=markdownLineStart,markdownItalic,@Spell,markdownLink,markdownLinkText concealends oneline
syntax region markdownBoldItalic matchgroup=markdownBoldItalicDelimiter start=" _ \*\*\S\@=" end="\S\@<=\*\*_\w\@!" skip="\\_\|\\\*" contains=markdownLineStart,@Spell,markdownLink,markdownLinkText concealends oneline
syntax region markdownBoldItalic matchgroup=markdownBoldItalicDelimiter start='\*\*_\S\@=' end='\S\@<=_\*\*\s\s' skip="\\_\|\\\*" contains=markdownLineStart,markdownItalic,@Spell,markdownLink,markdownLinkText concealends oneline

syntax region markdownLinkText matchgroup=markdownLinkTextDelimiter start="!\=\[\%(\%(\_[^][]\|\[\_[^][]*\]\)*]\%( \=[[(]\)\)\@=" end="\]\%( \=[[(]\)\@=" nextgroup=markdownLink,markdownId skipwhite contains=@markdownInline,markdownLineStart oneline
syntax region markdownLink matchgroup=markdownLinkDelimiter start="(" end=")" contains=mailURL keepend contained oneline
syntax region markdownId matchgroup=markdownIdDelimiter start="\[" end="\]" keepend contained oneline

syntax match  markdownH1 contains=@NoSpell,@markdownInline,mailURL '^## .\+$'
syntax match  markdownH2 contains=@NoSpell,@markdownInline,mailURL '^### .\+$'
syntax match  markdownH3 contains=@NoSpell,@markdownInline,mailURL '^#### .\+$'
syntax match  markdownH4 contains=@NoSpell,@markdownInline,mailURL '^##### .\+$'
syntax match  markdownH5 contains=@NoSpell,@markdownInline,mailURL '^###### .\+$'
syntax match  markdownH6 contains=@NoSpell,@markdownInline,mailURL '^####### .\+$'

highlight default link markdownH1                    Title
highlight default link markdownH2                    Title
highlight default link markdownH3                    Title
highlight default link markdownH4                    Title
highlight default link markdownH5                    Title
highlight default link markdownH6                    Title
highlight default link markdownHeadingRule           PreProc
highlight default link markdownH1Delimiter           Delimiter
highlight default link markdownH2Delimiter           Delimiter
highlight default link markdownH3Delimiter           Delimiter
highlight default link markdownH4Delimiter           Delimiter
highlight default link markdownH5Delimiter           Delimiter
highlight default link markdownH6Delimiter           Delimiter

highlight default link markdownLinkText              Underlined
highlight default link markdownId                    Type

highlight htmlBold       term=bold cterm=bold gui=bold
highlight htmlBoldItalic term=bold,italic cterm=bold,italic gui=bold,italic
highlight htmlItalic     term=italic cterm=italic gui=italic
highlight default link markdownBold                  htmlBold
highlight default link markdownBoldDelimiter         htmlBold
highlight default link markdownBoldItalic            htmlBoldItalic
highlight default link markdownBoldItalicDelimiter   htmlBoldItalic
highlight default link markdownItalic                htmlItalic
highlight default link markdownItalicDelimiter       htmlItalic

let b:current_syntax = 'notmuch-show'

let &cpoptions = s:cpo_save
unlet s:cpo_save
