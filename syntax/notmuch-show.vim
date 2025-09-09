vim9script
# Vim syntax file
# Language: notmuch-show window

# Quit when a syntax file was already loaded
if exists('b:current_syntax')
	finish
endif

set cpoptions&vim

syntax case ignore

matchadd('Conceal', '\m[\x0C]')
matchadd('Conceal', '\m[\u200B]')

execute 'source ' .. expand('<script>:p:h:h') .. '/macros/syntax-common.vim'

syntax match	mailNewPartHead	contained	contains=@NoSpell '^[\x0C].\+ part$'
syntax match	mailNewPartHead	contained	contains=@NoSpell '^[\x0C]HTML mail$'
syntax region	mailHeader	contained	contains=mailHeaderKey,mailNewPartHead,@mailHeaderField,@NoSpell start='^[\x0C].\+ part$' skip='^\s' end='^[^:]*\n' fold
syntax region	mailNewPart	contains=mailHeader,@HTMLmailBoldlock,@mailHeaderField,@NoSpell start='^[\x0C].\+ part$' end='^[\x0C]'me=e-1 fold
syntax region	mailNewPart	contains=mailHeader,@HTMLmailBoldlock,@mailHeaderField,@NoSpell start='^[\x0C].\+ mail$' end='^[\x0C]'me=e-1
syntax region	HTMLmail	contains=mailNewPartHead,@HTMLmailBoldlock,@NoSpell start='^[\x0C]HTML part$' end='^[\x0C]'me=e-1 end='\%$' fold
syntax region	HTMLmail	contains=mailNewPartHead,@HTMLmailBoldlock,@NoSpell start='^[\x0C]HTML mail$' end='^[\x0C]'me=e-1 end='\%$'

# marddown
# syntax cluster	HTMLmailInline	contains=HTMLmailLinkText,HTMLmailItalic,HTMLmailBold,HTMLmailBoldItalic
syntax cluster	HTMLmailInline	contains=HTMLmailLinkText,HTMLmailItalic,HTMLmailBold
syntax cluster	HTMLmailBoldlock	contains=HTMLmailH1,HTMLmailH2,HTMLmailH3,HTMLmailH4,HTMLmailH5,HTMLmailH6,@HTMLmailInline,HTMLmailLink,HTMLmailId

syntax region	HTMLmailItalic	contained	matchgroup=HTMLmailItalicTag start="_" end="_" skip="\\_"	contains=HTMLmailLinkBoldItalic,@Spell,HTMLmailLink,HTMLmailLinkText concealends keepend
syntax region	HTMLmailBold	contained	matchgroup=HTMLmailBoldTag start="\*\*" end="\*\*" skip="\\\*"	contains=HTMLmailLinkBoldItalic,@Spell,HTMLmailLink,HTMLmailLinkText concealends keepend
# syntax region	HTMLmailBoldItalic	contained	matchgroup=HTMLmailBoldItalicTag start="_\*\*" end="\*\*_\w\@!" skip="\\_\|\\\*"	contains=@Spell,HTMLmailLink,HTMLmailLinkText concealends keepend
# syntax region	HTMLmailBoldItalic	contained	matchgroup=HTMLmailBoldItalicTag start='\*\*_' end='_\*\*\s' skip="\\_\|\\\*"	contains=@Spell,HTMLmailLink,HTMLmailLinkText concealends keepend
syntax region	HTMLmailLinkBoldItalic	contained	matchgroup=HTMLmailBoldItalicTag start="_" end="_" skip="\\_"	contains=@Spell,HTMLmailLink,HTMLmailLinkText concealends keepend
syntax region	HTMLmailLinkBoldItalic	contained	matchgroup=HTMLmailBoldItalicTag start="\*\*" end="\*\*" skip="\\\*"	contains=@Spell,HTMLmailLink,HTMLmailLinkText concealends keepend

if get(g:, 'notmuch_conceal_url', 0)
	syntax region	HTMLmailLink	contained	matchgroup=HTMLmailLinkTag start="(" end=")"	contains=mailURL keepend oneline conceal
else
	syntax region	HTMLmailLink	contained	matchgroup=HTMLmailLinkTag start="(" end=")"	contains=mailURL keepend oneline
endif
syntax region	HTMLmailId	contained	matchgroup=HTMLmailIdTag start="\[" end="\]" keepend oneline
syntax region	HTMLmailLinkText	contained	matchgroup=HTMLmailLinkTextTag start="!\=\[\%(\%(\_[^][]\|\[\_[^][]*\]\)*]\%( \=[[(]\)\)\@=" end="\]\%( \=[[(]\)\@=" nextgroup=HTMLmailLink,HTMLmailId skipwhite	contains=@HTMLmailInline,HTMLmailLinkItalic,HTMLmailLinkBold keepend
syntax region	HTMLmailLinkItalic	contained	matchgroup=HTMLmailLinkItalicTag start="_" end="_"  skip="\\_"	contains=@Spell concealends keepend
syntax region	HTMLmailLinkBold	contained	matchgroup=HTMLmailLinkBoldTag start="\*\*" end="\*\*" skip="\\\*"	contains=@Spell concealends keepend

syntax match	HTMLmailH1	contained	contains=@NoSpell,@HTMLmailInline,mailURL '^#\{2} .\+$'
syntax match	HTMLmailH2	contained	contains=@NoSpell,@HTMLmailInline,mailURL '^#\{3} .\+$'
syntax match	HTMLmailH3	contained	contains=@NoSpell,@HTMLmailInline,mailURL '^#\{4} .\+$'
syntax match	HTMLmailH4	contained	contains=@NoSpell,@HTMLmailInline,mailURL '^#\{5} .\+$'
syntax match	HTMLmailH5	contained	contains=@NoSpell,@HTMLmailInline,mailURL '^#\{6} .\+$'
syntax match	HTMLmailH6	contained	contains=@NoSpell,@HTMLmailInline,mailURL '^#\{7} .\+$'

highlight default link HTMLmailH1	Title
highlight default link HTMLmailH2	Title
highlight default link HTMLmailH3	Title
highlight default link HTMLmailH4	Title
highlight default link HTMLmailH5	Title
highlight default link HTMLmailH6	Title
highlight default link HTMLmailLinkText	Underlined
highlight default link HTMLmailId	Type
highlight default link HTMLmailBold	htmlBold
highlight default link HTMLmailBoldTag	htmlBold
# highlight default link HTMLmailBoldItalic	htmlBoldItalic
highlight default link HTMLmailLinkBoldItalic	htmlBoldItalic
highlight default link HTMLmailBoldItalicTag htmlBoldItalic
highlight default link HTMLmailItalic	htmlItalic
highlight default link HTMLmailItalicTag	htmlItalic
highlight default link HTMLmailLinkItalic htmlLinkItalic
highlight default link HTMLmailLinkBold htmlLinkBold
highlight default link HTMLmailLinkItalicTag htmlLinkItalic
highlight default link HTMLmailLinkBoldTag htmlLinkBold

var hi_s: dict<any> = notmuch_py#Get_highlight('Normal')[0]
var htmlBold: dict<any> = extendnew(hi_s, {name: 'htmlBold', term: {bold: true}, cterm: {bold: true}, gui: {bold: true}})
var htmlItalic: dict<any> = extendnew(hi_s, {name: 'htmlItalic', term: {italic: true}, cterm: {italic: true}, gui: {italic: true}})
var htmlBoldItalic: dict<any> = extendnew(hi_s, {name: 'htmlBoldItalic', term: {italic: true, bold: true}, cterm: {italic: true, bold: true}, gui: {italic: true, bold: true}})
hi_s = notmuch_py#Get_highlight('Underlined')[0]
var htmlLinkItalic: dict<any> = extendnew(hi_s, {name: 'htmlLinkItalic', term: {bold: true, underline: true}, cterm: {bold: true, underline: true}, gui: {bold: true, underline: true}})
var htmlLinkBold: dict<any> = extendnew(hi_s, {name: 'htmlLinkBold', term: {italic: true, underline: true}, cterm: {italic: true, underline: true}, gui: {italic: true, underline: true}})
hlset([
	htmlBold,
	htmlItalic,
	htmlBoldItalic,
	htmlLinkItalic,
	htmlLinkBold,
])

b:current_syntax = 'notmuch-show'
