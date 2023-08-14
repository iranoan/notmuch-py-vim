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

syntax match	mailNewPartHead	contained	contains=@NoSpell '^[\x0C]\zs.\+ part$'
syntax match	mailNewPartHead	contained	contains=@NoSpell '^[\x0C]\zsHTML mail$'
syntax region	mailHeader	contained	contains=mailNewPartHead,@mailHeaderField,@NoSpell start='^[\x0C].\+ part$' skip='^\s' end='^[^:]*\n' fold
syntax region	mailNewPart	contains=mailHeader,@HTMLmailBlock,@mailHeaderField,@NoSpell start='^[\x0C].\+ \(part\|mail\)$' end='^[\x0C]'me=e-1 fold
syntax region	HTMLmail	contains=mailNewPartHead,@HTMLmailBlock,@NoSpell start='^[\x0C]HTML \%(mail\|part\)$' end='^[\x0C]'me=e-1 end='\%$' fold

" Usenet headers
syntax match	mailHeaderKey	contained	contains=mailHeaderEmail,mailEmail,@NoSpell /\v^[a-z-]+:\s*/
syntax region	mailHeader	contains=mailHideHeader,@mailHeaderField,@NoSpell start='\%^' skip='^\s' end='^$'me=s-1 end='^[\x0C]'me=e-1 fold

execute 'source ' .. expand('<sfile>:p:h:h') .. '/macros/syntax-common.vim'

 " marddown
syntax cluster	HTMLmailInline	contains=HTMLmailLinkTxt,HTMLmailItalic,HTMLmailB,HTMLmailBI
syntax cluster	HTMLmailBlock	contains=HTMLmailH1,HTMLmailH2,HTMLmailH3,HTMLmailH4,HTMLmailH5,HTMLmailH6,@HTMLmailInline,HTMLmailLink,HTMLmailId

syntax region	HTMLmailItalic	contained	matchgroup=HTMLmailItDelim start="_\S\@=" end="\S\@<=_" skip="\\_"	contains=HTMLmailLineStart,HTMLmailBI2,@Spell,HTMLmailLink,HTMLmailLinkTxt concealends keepend
syntax region	HTMLmailB	contained	matchgroup=HTMLmailBDelim start="\*\*\S\@=" end="\S\@<=\*\*" skip="\\\*"	contains=HTMLmailLineStart,HTMLmailBI2,@Spell,HTMLmailLink,HTMLmailLinkTxt concealends keepend
syntax region	HTMLmailBI	contained	matchgroup=HTMLmailItBDelim start="_\*\*\S\@=" end="\S\@<=\*\*_\w\@!" skip="\\_\|\\\*"	contains=HTMLmailLineStart,@Spell,HTMLmailLink,HTMLmailLinkTxt concealends keepend
syntax region	HTMLmailBI	contained	matchgroup=HTMLmailItBDelim start='\*\*_\S\@=' end='\S\@<=_\*\*\s' skip="\\_\|\\\*"	contains=HTMLmailLineStart,@Spell,HTMLmailLink,HTMLmailLinkTxt concealends keepend
syntax region	HTMLmailBI2	contained	matchgroup=HTMLmailItBDelim start="_\S\@=" end="\S\@<=_" skip="\\_"	contains=HTMLmailLineStart,@Spell,HTMLmailLink,HTMLmailLinkTxt concealends keepend
syntax region	HTMLmailBI2	contained	matchgroup=HTMLmailItBDelim start="\*\*\S\@=" end="\S\@<=\*\*" skip="\\\*"	contains=HTMLmailLineStart,@Spell,HTMLmailLink,HTMLmailLinkTxt concealends keepend

syntax region	HTMLmailLink	contained	matchgroup=HTMLmailLinkDelimiter start="(" end=")"	contains=mailURL keepend oneline
syntax region	HTMLmailId	contained	matchgroup=HTMLmailIdDelimiter start="\[" end="\]" keepend oneline
syntax region	HTMLmailLinkTxt	contained	matchgroup=HTMLmailLinkTextDelimiter start="!\=\[\%(\%(\_[^][]\|\[\_[^][]*\]\)*]\%( \=[[(]\)\)\@=" end="\]\%( \=[[(]\)\@=" nextgroup=HTMLmailLink,HTMLmailId skipwhite	contains=@HTMLmailInline,HTMLmailLineStart,HTMLmailLinkIt,HTMLmailLinkB oneline keepend
syntax region	HTMLmailLinkIt	contained	matchgroup=HTMLmailLinkITDelimiter start="_\S\@=" end="\S\@<=_"  skip="\\_"	contains=HTMLmailLineStart,@Spell concealends oneline keepend
syntax region	HTMLmailLinkB	contained	matchgroup=HTMLmailLinkBDelimiter start="\*\*\S\@=" end="\S\@<=\*\*" skip="\\\*"	contains=HTMLmailLineStart,@Spell concealends oneline keepend

syntax match	HTMLmailH1	contained	contains=@NoSpell,@HTMLmailInline,mailURL '^## .\+$'
syntax match	HTMLmailH2	contained	contains=@NoSpell,@HTMLmailInline,mailURL '^### .\+$'
syntax match	HTMLmailH3	contained	contains=@NoSpell,@HTMLmailInline,mailURL '^#### .\+$'
syntax match	HTMLmailH4	contained	contains=@NoSpell,@HTMLmailInline,mailURL '^##### .\+$'
syntax match	HTMLmailH5	contained	contains=@NoSpell,@HTMLmailInline,mailURL '^###### .\+$'
syntax match	HTMLmailH6	contained	contains=@NoSpell,@HTMLmailInline,mailURL '^####### .\+$'

highlight default link HTMLmailH1	Title
highlight default link HTMLmailH2	Title
highlight default link HTMLmailH3	Title
highlight default link HTMLmailH4	Title
highlight default link HTMLmailH5	Title
highlight default link HTMLmailH6	Title
highlight default link HTMLmailLinkTxt	Underlined
highlight default link HTMLmailId	Type
highlight default link HTMLmailB	htmlBold
highlight default link HTMLmailBDelim	htmlBold
highlight default link HTMLmailBI	htmlBoldItalic
highlight default link HTMLmailBI2	htmlBoldItalic
highlight default link HTMLmailItBDelim htmlBoldItalic
highlight default link HTMLmailItalic	htmlItalic
highlight default link HTMLmailItDelim	htmlItalic

let link_string = notmuch_py#Get_highlight('Underlined')
if link_string =~# '\<cterm='
	let link_it = substitute(link_string, '\<cterm=', 'cterm=italic,', 'g')
	let link_b = substitute(link_string, '\<cterm=', 'cterm=bold,', 'g')
else
	let link_it = link_string ..' cterm=italic'
	let link_b = link_string ..' cterm=bold'
endif
if link_string =~# '\<gui='
	let link_it = substitute(link_string, '\<gui=', 'gui=italic,', 'g')
	let link_b = substitute(link_string, '\<gui=', 'gui=bold,', 'g')
else
	let link_it = link_it ..' gui=italic'
	let link_b = link_b ..' gui=bold'
endif
execute 'highlight HTMLmailLinkIt ' .. link_it
execute 'highlight HTMLmailLinkB ' .. link_b
unlet link_string
unlet link_it
unlet link_b
highlight htmlBold       term=bold cterm=bold gui=bold
highlight htmlBoldItalic term=bold,italic cterm=bold,italic gui=bold,italic
highlight htmlItalic     term=italic cterm=italic gui=italic

let b:current_syntax = 'notmuch-show'

let &cpoptions = s:cpo_save
unlet s:cpo_save
