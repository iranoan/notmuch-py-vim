" notmuch-draft/show common part

" Syntax clusters
syntax cluster mailHeaderFields  contains=mailHeaderEmail,@mailLinks
syntax cluster mailLinks         contains=mailURL,mailEmail
syntax cluster mailQuoteExps     contains=mailQuoteExp1,mailQuoteExp2,mailQuoteExp3,mailQuoteExp4,mailQuoteExp5,mailQuoteExp6

execute 'syntax region mailHideHeader contained contains=mailHeaderKey,@mailHeaderFields,@NoSpell '
			\ . 'start=''^\(' . py3eval('get_hide_header()') . '\):'' skip=''^\s'' '
			\ . 'end=''' . '^\(' . join(g:notmuch_show_headers, '\|') . '\|\(Del-\)\?\(Attach\|HTML\)\|Fcc\|\(Not-\)\?Decrypted\|Encrypt\|PGP-Public-Key\|\(Good-\|Bad-\)\?Signature\):''me=s-1 '
			\ . 'end=''^$''  fold'
" execute 'syntax region mailHideHeader contained contains=mailHeaderKey,@mailHeaderFields,@NoSpell '
" 			\ . 'start=''\(' . join(g:notmuch_show_headers, '\|') . '\|\(Del-\)\?\(Attach\|HTML\)\|Fcc\|\(Not-\)\?Decrypted\|Encrypt\|PGP-Public-Key\|\(Good-\|Bad-\)\?Signature\)\@<!:'' skip=''^\s'' '
" 			\ . 'end=''' . '^\(' . join(g:notmuch_show_headers, '\|') . '\|\(Del-\)\?\(Attach\|HTML\)\|Fcc\|\(Not-\)\?Decrypted\|Encrypt\|PGP-Public-Key\|\(Good-\|Bad-\)\?Signature\):''me=s-1 '
" 			\ . 'end=''^$''  fold'
" execute 'syntax region mailHideHeader contained contains=mailHeaderKey,@mailHeaderFields,@NoSpell '
" 			\ . 'start=''' . '^\(' . join(g:notmuch_show_hide_headers, '\|')[:-2] . '\|X-[a-z-]\+\):'' skip=''^\s'' '
" 			\ . 'end=''' . '^\(' . join(g:notmuch_show_headers, '\|')[:-2] . '\|\(Del-\)\?\(Attach\|HTML\)\|Fcc\|\(Not-\)\?Decrypted\|Encrypt\|PGP-Public-Key\|\(Good-\|Bad-\)\?Signature\):''me=s-1 '
" 			\ . 'end=''^$''  fold'

" Anything in the header between < and > is an email address
syntax match  mailHeaderEmail contained contains=@NoSpell '<.\{-}>'

" Mail Signatures. (Begin with "-- ", end with change in quote level)
syntax region mailSignature keepend contains=@mailLinks,@mailQuoteExps start='^--\s$' end='^$' end='^\(> \?\)\+'me=s-1 fold
syntax region mailSignature keepend contains=@mailLinks,@mailQuoteExps,@NoSpell start='^\z(\(> \?\)\+\)--\s$' end='^\z1$' end='^\z1\@!'me=s-1 end='^\z1\(> \?\)\+'me=s-1 fold

" Treat verbatim Text special.
syntax region  mailVerbatim contains=@NoSpell keepend start='^#v+$' end='^#v-$' fold
syntax region  mailVerbatim contains=@mailQuoteExps,@NoSpell keepend start='^\z(\(> \?\)\+\)#v+$' end='\z1#v-$' fold

" URLs start with a known protocol or www,web,w3.
syntax match mailURL contains=@NoSpell '\v<(((https?|ftp|gopher)://|(mailto|file|news):)[^' \t<>"]+|(www|web|w3)[a-z0-9_-]*\.[a-z0-9._-]+\.[^' \t<>"]+)[a-z0-9/]'
syntax match mailEmail contains=@NoSpell '\v[_=a-z\./+0-9-]+\@[a-z0-9._-]+\a{2}'

" Make sure quote markers in regions (header / signature) have correct color
syntax match mailQuoteExp1 contained '\v^(\> ?)'
syntax match mailQuoteExp2 contained '\v^(\> ?){2}'
syntax match mailQuoteExp3 contained '\v^(\> ?){3}'
syntax match mailQuoteExp4 contained '\v^(\> ?){4}'
syntax match mailQuoteExp5 contained '\v^(\> ?){5}'
syntax match mailQuoteExp6 contained '\v^(\> ?){6}'

" Even and odd quoted lines. Order is important here!
syntax region  mailQuoted6  keepend contains=mailVerbatim,mailHeader,mailHeader2,@mailLinks,mailSignature,@NoSpell start='^\z(\(\([a-z]\+>\|[]}>]\)[ \t]*\)\{5}\([a-z]\+>\|[]}>]\)\)' end='^\z1\@!' fold
syntax region  mailQuoted5  keepend contains=mailQuoted6,mailVerbatim,mailHeader,mailHeader2,@mailLinks,mailSignature,@NoSpell start='^\z(\(\([a-z]\+>\|[]}>]\)[ \t]*\)\{4}\([a-z]\+>\|[]}>]\)\)' end='^\z1\@!' fold
syntax region  mailQuoted4  keepend contains=mailQuoted5,mailQuoted6,mailVerbatim,mailHeader,mailHeader2,@mailLinks,mailSignature,@NoSpell start='^\z(\(\([a-z]\+>\|[]}>]\)[ \t]*\)\{3}\([a-z]\+>\|[]}>]\)\)' end='^\z1\@!' fold
syntax region  mailQuoted3  keepend contains=mailQuoted4,mailQuoted5,mailQuoted6,mailVerbatim,mailHeader,mailHeader2,@mailLinks,mailSignature,@NoSpell start='^\z(\(\([a-z]\+>\|[]}>]\)[ \t]*\)\{2}\([a-z]\+>\|[]}>]\)\)' end='^\z1\@!' fold
syntax region  mailQuoted2  keepend contains=mailQuoted3,mailQuoted4,mailQuoted5,mailQuoted6,mailVerbatim,mailHeader,mailHeader2,@mailLinks,mailSignature,@NoSpell start='^\z(\(\([a-z]\+>\|[]}>]\)[ \t]*\)\{1}\([a-z]\+>\|[]}>]\)\)' end='^\z1\@!' fold
syntax region  mailQuoted1  keepend contains=mailQuoted2,mailQuoted3,mailQuoted4,mailQuoted5,mailQuoted6,mailVerbatim,mailHeader,mailHeader2,@mailLinks,mailSignature,@NoSpell start='^\z([a-z]\+>\|[]}>]\)' end='^\z1\@!' fold

" Need to sync on the header. Assume we can do that within 100 lines
if exists('mail_minlines')
	execute 'syn sync minlines=' . mail_minlines
else
	syntax sync minlines=100
endif

" Define the default highlighting.
highlight def link mailVerbatim    Special
highlight def link mailHideHeader  Statement
highlight def link mailHeaderKey   Type
highlight def link mailSignature   PreProc
highlight def link mailHeaderEmail mailEmail
highlight def link mailEmail       Special
highlight def link mailURL         String
highlight def link mailQuoted1     Comment
highlight def link mailQuoted3     mailQuoted1
highlight def link mailQuoted5     mailQuoted1
highlight def link mailQuoted2     Identifier
highlight def link mailQuoted4     mailQuoted2
highlight def link mailQuoted6     mailQuoted2
highlight def link mailQuoteExp1   mailQuoted1
highlight def link mailQuoteExp2   mailQuoted2
highlight def link mailQuoteExp3   mailQuoted3
highlight def link mailQuoteExp4   mailQuoted4
highlight def link mailQuoteExp5   mailQuoted5
highlight def link mailQuoteExp6   mailQuoted6
highlight def link mailHeader      Statement
highlight mailNewPartHead term=reverse,bold gui=reverse,bold
