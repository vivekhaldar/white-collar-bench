"""Built-in vocabulary that keeps the privacy scanner quiet about ordinary words.

The leak scanner (`wcb.privacy.scan`) flags capitalized words, runs of capitalized words and
word 6-grams that occur both in a private repository and in the benchmark corpus. Most such
overlaps are harmless: sentence-initial words ("Thanks", "Please"), title-case headings
("Next Steps"), calendar words ("Monday"), tool names ("Slack") and very common personal names.
This module lists that vocabulary so the scanner can ignore it or downgrade it.

All lists are lowercase. Lookups in the scanner are case-insensitive and accent-insensitive, and
`COMMON_WORDS` is also matched after stripping common English suffixes (so "planned",
"planning" and "plans" all count as the common word "plan").

Sets:

- `COMMON_WORDS`: everyday English words, including workplace vocabulary.
- `MONTHS`, `WEEKDAYS`, `CALENDAR_WORDS`: never reported, even when capitalized.
- `PLACES`: countries, US states, major world cities, regions, nationalities and languages.
  Real places are not private on their own.
- `TECH_TERMS`: generic technology and business vocabulary (products, file formats, protocol
  keywords, acronyms).
- `FIRST_NAMES`, `SURNAMES`: very common personal names. A single matching name is reported
  with severity "low" rather than "medium"; a run such as "Firstname Lastname" is still "high".

These are generic public word lists. They are not derived from any private repository.
"""

from __future__ import annotations

import builtins


def _words(text: str) -> frozenset[str]:
    return frozenset(w.lower() for w in text.split())


COMMON_WORDS = _words(
    """
    a able about above abroad absence absent absolute absolutely absorb abstract abuse academic
    accept acceptable acceptance access accessible accident accommodate accompany accomplish
    according accordingly account accountability accountable accounting accrual accurate accuracy
    accuse achieve achievement acknowledge acquire acquisition across act action active activity
    actor actual actually acute ad adapt adaptation add addition additional address adequate
    adjust adjustment administration administrative admin admit adopt adoption adult advance
    advanced advantage adventure adverse advertise advertising advice advise adviser advisor
    advisory advocate affair affect afford afraid after afternoon afterward afterwards again
    against age agency agenda agent aggregate aggressive ago agree agreement ahead aid aim air
    aircraft airline airport alarm album alert align alignment alike alive all allocate
    allocation allow allowance almost alone along alongside already also alter alternative
    although altogether always am amazing ambition ambitious amend amendment among amongst amount
    ample analysis analyst analytics analyze analyse ancient and anger angle angry animal
    anniversary announce announcement annual annually another answer anticipate anxiety anxious
    any anybody anymore anyone anything anyway anywhere apart apartment apologize apologise
    apology apparent apparently appeal appear appearance apple applicable applicant application
    apply appoint appointment appreciate appreciation approach appropriate approval approve
    approximate approximately arbitrary architect architecture archive are area argue argument
    arise arm army around arrange arrangement array arrest arrival arrive art article artifact
    artefact artist artistic as aside ask aspect assess assessment asset assign assignment
    assist assistance assistant associate associated association assume assumption assure at
    atmosphere attach attachment attack attempt attend attendance attendee attention attitude
    attorney attract attractive attribute audience audio audit author authority authorize
    authorise auto automatic automatically automation availability available avenue average avoid
    await award aware awareness away awesome awful awkward

    baby back backend background backlog backup bad badly bag balance ball ban band bank bar
    barely barrier base baseline basic basically basis basket bat batch bath battery battle bay
    be beach bear beat beautiful beauty became because become bed bedroom been beer before
    began begin beginning behalf behave behavior behaviour behind being belief believe bell
    belong below belt bench benchmark beneficial benefit beside besides best bet better between
    beyond bid big bike bill billing billion bind binder bird birth birthday bit bite black
    blame blank blind block blocked blocker blog blood blow blue board boat body bold bond bonus
    book booking boost boot border bored boring born borrow boss both bother bottle bottleneck
    bottom bought bound boundary bowl box boy brain branch brand brave bread break breakdown
    breakfast breath breathe brick bridge brief briefing briefly bright brilliant bring broad
    broadcast broke broken brother brought brown browser brush buck budget buffer bug build
    builder building built bulk bullet bump bunch burden burn burst bus business busy but
    butter button buy buyer buzz by bye

    cabinet cable cafe cake calculate calculation calendar call calm came camera camp campaign
    campus can cancel cancellation cancer candidate cap capability capable capacity capital
    captain capture car card care career careful carefully carry cart case cash cast casual cat
    catalog catalogue catch category caught cause caution cell center centre central century
    ceremony certain certainly certificate certification chain chair chairman chairperson
    challenge champion chance change channel chapter character characteristic charge chart
    charter chase chat cheap check checklist checkpoint cheer cheers cheese chef chemical chest
    chicken chief child childhood children choice choose chose chosen church circle circulate
    circumstance cite citizen city civil claim clarify clarification class classic classify
    classroom clean clear clearly clerk click client climate climb clinic clinical clock close
    closely closure cloud club clue cluster coach coal coast coat code coffee cognitive cohort
    cold collaborate collaboration collapse colleague collect collection collective college color
    colour column combination combine come comfort comfortable coming command comment commerce
    commercial commission commit commitment committee common commonly communicate communication
    community company compare comparison compatible compensation compete competition competitive
    competitor compile complain complaint complete completely completion complex compliance
    complicated comply component compose comprehensive compromise compute computer concentrate
    concept concern concerned concerning concert conclude conclusion concrete condition conduct
    conference confidence confident confidential configure confirm confirmation conflict confused
    confusion congrats congratulations connect connection conscious consensus consent
    consequence consequential conservative consider considerable consideration consist consistent constant
    constantly constraint construct construction consult consultant consultation consume
    consumer contact contain container content contest context continue continuous contract
    contractor contrast contribute contribution control controversial convene convention
    conversation conversion convert convince cook cookie cool cooperation coordinate
    coordination coordinator cope copy core corner corporate corporation correct correction
    correctly correlation correspond cost could council counsel count counter country county
    couple courage course court cousin cover coverage crack craft crash crazy create creation
    creative credit crew crime criminal crisis criteria criterion critical criticism critique
    cross crowd crucial cry cultural culture cup curious currency current currently curriculum
    custom customer cut cycle

    dad daily damage dance danger dangerous dark dashboard data database date daughter day dead
    deadline deal dealer dear death debate debt debug decade decent decide decision deck declare
    decline decrease dedicated deep deeply default defeat defend defense defence defer define
    definitely definition degree delay delegate delete deliberately delicate delight deliver
    deliverable delivery demand demo democracy democratic demonstrate denial deny department
    depend dependency dependent deploy deployment deposit depot depth deputy derive describe
    description desert deserve design designer desire desk desktop despite detail detailed
    detect determine develop developer development device devote diagram dial dialog dialogue
    did diet differ difference different difficult difficulty dig digest digital dimension
    dinner direct direction directly director directory dirty disability disagree disappear
    disaster discount discover discovery discuss discussion disease dish dismiss display
    dispute distance distinct distinguish distribute distribution district diverse divide
    division divorce do doc doctor document documentation does dog doing dollar domain domestic
    dominant done door double doubt down download downstream downtime downtown dozen draft drag
    drama dramatic draw drawing drawn dream dress drew drink drive driven driver drop drove drug
    dry due dull duplicate during dust duty dynamic

    each eager ear early earn earnings earth ease easily east eastern easy eat economic economy
    edge edit edition editor educate education effect effective effectively efficiency efficient
    effort egg eight eighteen eighty either elderly elect election electric electricity
    electronic element elevator eleven eligible eliminate else elsewhere email embed embrace
    emerge emergency emotion emotional emphasis emphasize employ employee employer employment
    empty enable encounter encourage end ending endorse endorsement endpoint enemy energy enforce
    engage engagement engine engineer engineering enhance enjoy enormous enough enroll ensure
    enter enterprise entertainment enthusiasm entire entirely entitle entity entrance entry
    environment environmental episode equal equally equipment equity equivalent era error
    escalate escalation escape especially essay essential establish estate estimate etc evaluate
    evaluation even evening event eventually ever every everybody everyday everyone everything
    everywhere evidence evil evolve exact exactly exam examination examine example exceed
    excellent except exception exchange excited excitement exciting exclude exclusive excuse
    execute execution executive exercise exhibit exist existence existing exit expand expansion
    expect expectation expedite expense expensive experience experiment expert expertise expire
    explain explanation explicit explore export expose exposure express expression extend
    extension extent external extra extract extraordinary extreme extremely eye

    face facilitate facility fact factor factory fail failure fair fairly faith fall false
    familiar family famous fan fancy fantastic far farm farmer fashion fast fat father fault
    favor favour favorite favourite fear feasible feature fee feed feedback feel feeling fell
    fellow felt female fence festival few field fifteen fifth fifty fight figure file fill film
    filter final finalize finally finance financial find finding fine finger finish fire firm
    first fiscal fish fit five fix fixed flag flat flexible flight float floor flow flower fly freight
    focus fold folder folk follow followup following food foot football for force forecast
    foreign forest forever forget forgive forgot form formal format former formula forth
    fortune forty forum forward found foundation founder four fourteen fourth frame framework
    free freedom freeze frequency frequent frequently fresh friend friendly from front frontend
    fruit fuel full fully fun function functional fund funding funny furniture further future

    gain game gap garage garden gas gate gather gauge gave gear general generally generate
    generation generous gentle genuine get giant gift girl give given glad glass global go goal
    god goes going gold golden golf gone good goodbye goods got govern governance government grab
    grade gradually graduate grand grant graph grass grateful gray great green grew grey grid
    ground group grow grown growth guarantee guard guess guest guidance guide guideline guilty
    gun guy

    habit had hair half hall hand handle handled handoff handover hang happen happy hard hardly
    hardware harm has hat hate have having he head headline headquarters health healthy hear
    heard hearing heart heat heavy height held hello help helpful hence her here hero herself hey
    hi hide high highlight highly him himself hint hire his historic historical history hit hold
    hole holiday home honest honestly honor honour hope horizon horse hospital host hot hotel hour
    house household housing how however huge human humor humour hundred hungry hunt hurry hurt
    husband

    i ice idea ideal identical identify identity idle if ignore ill illegal illustrate image
    imagine immediate immediately impact implement implementation implication imply import
    importance important impose impossible impress impression impressive improve improvement in
    inbox incentive incident include including income incorporate increase increasingly
    incredible indeed independent index indicate indication indicator individual industrial
    industry inevitable infant inflation influence inform informal information infrastructure
    initial initially initiative injury inner innovation innovative input inquiry inside insight
    insist inspect inspection inspire install installation instance instead institute
    institution instruction instrument insurance intake integrate integration intellectual
    intelligence intend intense intention interaction interest interested interesting interface
    interim internal international internet interpret interpretation interview into introduce
    introduction invest investigate investigation investment investor invitation invite invoice
    involve involved iron is island issue it item its itself

    jacket job join joint joke journal journey joy judge judgment judgement jump junior jury just
    justice justify

    keen keep kept key keyboard kick kickoff kid kill kind kindly king kitchen knee knew knife
    knock know knowledge known

    lab label labor labour lack lady laid land landscape language laptop large largely last late
    later latest latter laugh launch law lawyer lay layer lead leader leadership leading leaf
    league lean learn learning least leave lecture led ledger left leg legacy legal legislation lend
    length less lesson let letter level liability library licence license lie life lift light
    like likely limit limitation limited line link list listen literally literature little live
    living load loan local locate location lock log logic logical login logistics long look loop
    loose lose loss lost lot loud love lovely low lower loyal luck lucky lunch

    machine mad made magazine mail main mainly maintain maintenance major majority make maker
    making male mall man manage management manager mandate manner manual manufacturer
    manufacturing many map margin mark market marketing marriage married mass massive master
    match material matter maximum maybe me meal mean meaning means meant meanwhile measure
    measurement meat media medical medicine medium meet meeting member membership memo memory
    men mental mention mentor menu mere merely merge message met metal method metric middle
    midnight might migrate migration mile milestone military milk million mind mine minimum
    minister minor minority minute minutes mirror miss mission mistake mix mixed mobile mode
    model moderate modern modest modify module moment money monitor month monthly mood moral
    more moreover morning mortgage most mostly mother motion motivation motor mount mountain
    mouse mouth move movement movie much multiple municipal museum music must mutual my myself
    mystery

    nail name narrative narrow nation national native natural naturally nature near nearby
    nearly neat necessarily necessary neck need negative negotiate negotiation neighbor
    neighbour neighborhood neighbourhood neither nervous net network neutral never nevertheless
    new newly news newsletter next nice night nine nineteen ninety no nobody nod noise none noon
    nor normal normally north northern nose not note nothing notice notification notion novel
    now nowhere nuclear number numerous nurse

    object objection objective obligation observe obtain obvious obviously occasion occasionally
    occupy occur ocean odd of off offer office officer official often oh oil ok okay old on
    onboard onboarding once one ongoing online only onto open opening operate operation
    operational operator opinion opponent opportunity oppose opposite option optional or oral
    orange order ordinary organic organization organisation organize organise origin original
    other otherwise ought our ours ourselves out outage outcome outline output outside
    outstanding over overall overcome overdue overview owe own owner ownership

    pace pack package page paid pain paint pair panel panic paper paragraph parent park parking
    part participant participate participation particular particularly partly partner
    partnership party pass passage passenger passcode passion passionate password past patch path patient
    pattern pause pay payment payroll peace peak peer pen penalty pending people pepper per
    perceive percent percentage perception perfect perfectly perform performance perhaps period
    permanent permission permit person personal personally personnel perspective phase phone
    photo phrase physical pick picture piece pilot pin pipeline pitch place plain plan plane
    planet planning plant plate platform play player pleasant please pleased pleasure plenty
    plot plus pocket podcast poem poet point police policy political politics poll pool poor pop
    popular population port portal portfolio portion position positive possess possession
    possibility possible possibly post poster postpone pot potato potential pound pour poverty
    power powerful practical practice practise praise pray precise prefer preference pregnant
    preliminary premium preparation prepare presence present presentation preserve president
    press pressure presumably pretty prevent preview previous previously price pricing pride
    primary prime principal principle print prior priority prison privacy private prize
    probably problem procedure proceed process procurement produce producer product production
    productive productivity profession professional professor profile profit program programme
    progress prohibit project prominent promise promote promotion prompt proof proper properly
    property proportion proposal propose prospect protect protection protein protest protocol
    prototype proud prove provide provider province provision public publication publicly
    publish pull punch purchase pure purple purpose pursue push put

    qualify quality quantity quarter quarterly queen query question questionnaire queue quick
    quickly quiet quietly quit quite quote

    race radical radio rail rain raise ran random range rank rapid rapidly rare rarely rate
    rather rating ratio raw reach react reaction read reader readiness reading ready real
    reality realize realise really reason reasonable rebuild recall recap receipt receive recent
    recently reception recipe recognize recognise recommend recommendation reconcile
    reconciliation record recording recover recovery recruit recruiter recurring red redo
    reduce reduction refer reference reflect reform refresh refund refuse regard regarding
    regards region regional register regular regularly regulation regulator regulatory reject
    relate relation relationship relative relatively relax release relevant reliable relief
    religion religious rely remain remaining remark remarkable remember remind reminder remote
    remove renew renewal rent reopen repair repeat replace replacement replied reply report
    reporter repository represent representative reputation request require requirement rescue
    research researcher reservation reserve reset resident resign resist resolution resolve
    resource respect respond response responsibility responsible rest restaurant restore
    restrict restriction result resume retail retain retire retirement retreat retro
    retrospective return reveal revenue reverse review revise revision revisit reward rework
    rich rid ride right ring rise risk river road roadmap rock role roll rollback rollout
    romantic roof room root rough round route routine row royal rule run running rural rush

    sad safe safety said sake salary sale sales salt same sample sand sandbox sat satisfaction
    satisfy save saving saw say scale scenario scene schedule scheme school science scientific
    scientist scope score screen script sea search season seat second secondary secret secretary
    section sector secure security see seed seek seem seen segment seize select selection self
    sell send senior sense sensitive sent sentence separate sequence series serious seriously
    servant serve server service session set setting settle settlement setup seven seventeen
    seventy several severe sex shadow shake shall shape share sharp she sheet shelf shell shift
    shine ship shipment shirt shock shoe shoot shop shopping short shortly shot should shoulder
    shout show shower shut sick side sight sign signal signature significant significantly
    signoff silence silent silly silver similar simple simply since sing single sink sir sister
    sit site situation six sixteen sixty size skill skin skip sky slack sleep slide slight
    slightly slip slot slow slowly small smart smell smile smoke smooth snap snow so social
    society soft software soil sold solid solution solve some somebody somehow someone
    something sometime sometimes somewhat somewhere son song soon sorry sort soul sound source
    south southern space spare speak speaker special specialist specific specifically specify
    speech speed spend spent spirit split spoke spokesperson sponsor sport spot spread
    spreadsheet spring sprint square squeeze stable staff stage stake stakeholder stand standard
    standup star start state statement station statistic statistics status stay steady steal
    step stick still stock stone stood stop storage store storm story straight strange stranger
    strategic strategy stream street strength strengthen stress stretch strict strike string
    strong strongly structure struggle student studio study stuff stupid style subject submit
    subscription subsequent substantial succeed success successful successfully such sudden
    suddenly suffer sufficient sugar suggest suggestion suit suitable summary summer summit sun
    super supplier supply support supporter suppose sure surely surface surgery surprise
    surprised surprising surround survey survive suspect sustain sustainable swap sweet swim
    switch symbol sync system

    table tackle tag tail take taken tale talent talk tall target task taste tax tea teach
    teacher teaching team tear technical technique technology telephone television tell
    temperature template temporary ten tenant tend tendency tension term terms terrible
    territory test testing text than thank thanks that the theater theatre their theirs them
    theme themselves then theory therapy there therefore these they thick thin thing think
    thinking third thirteen thirty this thorough those though thought thousand thread threat
    threaten three threshold through throughout throw thus ticket tie tier tight till time
    timeline timely timing tiny tip tired title to today together toilet told tomorrow tone
    tonight too took tool tooth top topic total totally touch touchpoint tough tour tourist
    toward towards tower town track trade tradition traditional traffic train training
    transaction transcript transfer transform transformation transition translate translation
    transport transportation trap travel treat treatment tree trend trial trigger trip trouble
    truck true truly trust truth try tube tune turn twelve twenty twice two type typical
    typically

    ugly ultimate ultimately unable uncle under undergo understand understanding understood
    unfortunately uniform union unique unit unite united universal universe university unknown
    unless unlike unlikely until unusual up upcoming update upgrade upon upper upset upstream
    urban urge urgent us usage use used useful user usual usually utility

    vacation valid validate validation valley valuable value variable variance variation variety
    various vary vast vehicle vendor venture venue verify version versus very via vice victim
    victory video view viewer village violence virtual virtually visible vision visit visitor
    visual vital voice volume voluntary volunteer vote

    wage wait wake walk wall want war warm warn warning was wash waste watch water wave way we
    weak weakness wealth weapon wear weather web website wedding week weekend weekly weigh weight
    welcome welfare well went were west western wet what whatever wheel when whenever where
    whereas wherever whether which while whilst white who whole whom whose why wide widely wife
    wild will willing win wind window wine wing winner winter wire wise wish with withdraw
    within without witness woman women won wonder wonderful wood wooden word wore work worker
    workflow workforce working workload workshop workspace workstream world worried worry worse
    worst worth would wrap write writer writing written wrong wrote

    yard yeah year yearly yellow yes yesterday yet yield you young your yours yourself
    yourselves youth zero zone

    ago anyhow aboard beneath despite except inside onto outside underneath unto upon versus
    whereby wherein hereby herein thereby therein thereof hereof whatsoever whichever whoever
    nonetheless notwithstanding moreover furthermore likewise otherwise regardless respectively

    i'm i've i'd i'll you're you've you'll you'd he's he'd he'll she's she'd she'll it's it'd
    it'll we're we've we'll we'd they're they've they'll they'd that's there's here's what's
    where's who's how's let's don't doesn't didn't can't cannot won't wouldn't shouldn't
    couldn't isn't aren't wasn't weren't hasn't haven't hadn't mustn't needn't ain't y'all

    mr mrs ms miss dr prof sir madam dear hi hey hello hiya greetings thanks thank cheers best
    regards sincerely warmly cordially kind fyi pls plz thx ty np btw imo imho aka asap tbd tbc
    tba eod eow eta ooo pto wfh rsvp ps nb re fw fwd cc bcc

    one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen
    sixteen seventeen eighteen nineteen twenty thirty forty fifty sixty seventy eighty ninety
    hundred thousand million billion trillion first second third fourth fifth sixth seventh
    eighth ninth tenth half quarter dozen once twice triple double single zero none

    red orange yellow green blue purple violet pink brown black white gray grey silver gold
    golden bronze copper amber azure crimson scarlet indigo navy teal cyan magenta beige ivory
    maroon olive coral emerald ruby jade

    action items notes agenda attendees decisions risks assumptions dependencies goals scope
    requirements highlights lowlights blockers updates appendix glossary faq overview
    background context summary introduction conclusion abstract results findings recommendations
    next steps open questions discussion minutes recap followups follow-ups todo todos

    north south east west northern southern eastern western central northeast northwest
    southeast southwest upper lower inner outer middle mid greater
    harbor harbour port bay river lake creek brook spring springs falls hill hills mount mountain
    valley ridge canyon island isle coast shore beach park garden gardens field fields meadow
    forest wood woods grove glen dale vale heath moor marsh pond bridge ford mill mills street
    road avenue lane drive way boulevard plaza square court place terrace crescent circle
    highway route station terminal tower towers center centre gate gates point landing crossing
    junction corridor district quarter village town city county state province region territory
    capital metro downtown uptown midtown suburb campus estate manor castle hall abbey church

    cat dog bird fish horse cow pig sheep goat chicken duck goose rabbit mouse rat bear wolf fox
    deer lion tiger elephant monkey whale dolphin shark eagle hawk owl crow raven swan dove
    falcon heron otter beaver badger squirrel bee ant butterfly spider snake frog turtle
    oak pine maple birch cedar willow elm ash rose lily daisy tulip ivy fern moss clover

    stone rock iron steel copper glass wood paper plastic cotton wool silk leather brick
    concrete clay sand salt sugar water fire earth air wind rain snow ice storm cloud sun moon
    star sky light dark shadow dawn dusk morning evening night noon midday midnight season
    spring summer autumn fall winter

    accordance additionally admittedly afterward albeit alternatively apparently arguably
    basically certainly clearly conversely currently definitely essentially eventually evidently
    exactly finally fortunately frankly generally hopefully ideally importantly incidentally
    increasingly initially instead interestingly lately luckily meanwhile mostly namely
    naturally necessarily normally notably obviously occasionally originally overall
    particularly perhaps personally possibly potentially presumably previously primarily
    probably quickly rarely realistically recently relatively roughly seemingly separately
    seriously shortly significantly similarly simply slightly specifically strictly
    subsequently successfully suddenly supposedly surely technically temporarily thankfully
    thereafter thoroughly truly typically ultimately unfortunately usually virtually

    agile align ambiguity anchor annex appendix approver archive asynchronous audit backfill
    bandwidth benchmark bespoke bid bottleneck brainstorm briefing buyin cadence capex
    cascade charter churn circle clarity collateral compliance contingency counterpart
    crossfunctional dashboard deadline debrief deck deepdive delegate deliverable dependency
    deprecate digest discovery downstream draft dry-run due diligence endorsement escalate
    estimate fallback feasibility forecast framework friction gating governance handoff
    headcount holdup hypothesis incumbent initiative intake iteration kickoff landscape latency
    leverage liaison lineup logistics memo merger metric milestone mitigation momentum
    negotiation offboarding offsite onsite opex outreach overhaul owner pain playbook
    postmortem prereq prerequisite prioritize prioritise procurement proposal prototype
    quota readout rebaseline redline refactor renewal reorg reorganization requisition
    retainer retro rollout runbook runway scorecard shortlist signoff sizing slippage
    stakeholder standup statement steerco steering streamline sunset swimlane synergy
    takeaway taskforce teardown tender throughput timebox touchbase tracker triage turnaround
    underway uplift upsell utilization vendor walkthrough waiver watchlist webinar whitepaper workaround
    workstream writeup

    accountant administrator advisor analyst architect assistant associate auditor buyer
    chair chairman chairwoman champion chief clerk coach consultant contractor coordinator
    counsel designer developer director economist editor engineer executive facilitator
    founder head inspector intern investor lawyer lead liaison manager mentor officer operator
    owner paralegal partner planner president principal producer programmer recruiter
    representative researcher reviewer scientist secretary specialist sponsor staff steward
    strategist student supervisor supplier surveyor teacher technician trainee treasurer
    trustee tutor vendor volunteer

    ablation accuracy adapter aggregate algorithm annotate annotation annotator app apps
    attribution automate automated bare baseline benchmark binary blunt bubbly cache calibrate
    calibration chancellor chemistry classifier collegial compose compositional concentrate
    config configuration controllable convey corpus corpora crisp dataset debug deterministic
    determinism diagnose diagnosis diagnostic disable dock dual embedding energetic enthusiastic
    evaluator fulfil fulfill generator gracious grader hallucinate hallucination harness
    heterogeneous homogeneous heuristic holistic hyperparameter incremental inference ingest
    ingestion invisible isolate isolation layout leaderboard leak leftover lifetime linear
    literal macro manifest methodical metadata micro multi noisy oracle orchestrate
    orchestration parallel parse parser pipeline planner polite practitioner precision recall
    redundant renderer reproduce reproducible retrieval retrieve retry rubric runtime salesy
    scatter scorer scoring simulate simulation simulator skew stopword suite supersede symptom
    synthesis synthetic throughput timeout token toolkit troubleshoot unsent upbeat validator
    vector workbench milestone horizon summit momentum caveat invent invention inventory dump
    lookup fallback workaround placeholder

    account accounts admin board compliance customer customers design engineering facilities
    finance growth hr infrastructure it legal marketing ops operations partnerships people
    platform procurement product purchasing quality research revenue risk sales security
    services strategy success support talent treasury
    """
)

MONTHS = _words(
    """
    january february march april may june july august september october november december
    jan feb mar apr jun jul aug sep sept oct nov dec
    """
)

WEEKDAYS = _words(
    """
    monday tuesday wednesday thursday friday saturday sunday
    mon tue tues wed weds thu thur thurs fri sat sun weekday weekdays weekend weekends
    """
)

CALENDAR_WORDS = _words(
    """
    today tomorrow yesterday tonight morning afternoon evening noon midnight am pm
    christmas xmas easter thanksgiving halloween hanukkah chanukah diwali ramadan eid passover
    kwanzaa newyear juneteenth memorial labor labour independence veterans presidents
    boxing whitsun pentecost lent advent holiday holidays vacation sabbatical
    utc gmt bst cet cest est edt cst cdt mst mdt pst pdt ist jst aest aedt
    q1 q2 q3 q4 h1 h2 fy ytd mtd qtd
    """
)

PLACES = _words(
    """
    africa america americas antarctica arctic asia atlantic australia caribbean europe eurasia
    mediterranean oceania pacific scandinavia balkans baltic iberia latin levant nordic
    midwest northeast southwest southeast northwest

    afghanistan albania algeria andorra angola argentina armenia austria azerbaijan bahamas
    bahrain bangladesh barbados belarus belgium belize benin bhutan bolivia bosnia botswana
    brazil brunei bulgaria burkina burundi cambodia cameroon canada chad chile china colombia
    congo croatia cuba cyprus czechia czech denmark djibouti dominica ecuador egypt el salvador
    england eritrea estonia eswatini ethiopia fiji finland france gabon gambia georgia germany
    ghana greece grenada guatemala guinea guyana haiti honduras hungary iceland india indonesia
    iran iraq ireland israel italy jamaica japan jordan kazakhstan kenya korea kosovo kuwait
    kyrgyzstan laos latvia lebanon lesotho liberia libya liechtenstein lithuania luxembourg
    madagascar malawi malaysia maldives mali malta mauritania mauritius mexico moldova monaco
    mongolia montenegro morocco mozambique myanmar namibia nepal netherlands holland zealand
    nicaragua niger nigeria norway oman pakistan palestine panama paraguay peru philippines
    poland portugal qatar romania russia rwanda samoa scotland senegal serbia seychelles sierra
    leone singapore slovakia slovenia somalia spain sri lanka sudan suriname sweden switzerland
    syria taiwan tajikistan tanzania thailand togo tonga trinidad tobago tunisia turkey turkiye
    turkmenistan uganda ukraine emirates uae uk usa us britain kingdom states uruguay uzbekistan
    vanuatu vatican venezuela vietnam wales yemen zambia zimbabwe

    alabama alaska arizona arkansas california colorado connecticut delaware florida georgia
    hawaii idaho illinois indiana iowa kansas kentucky louisiana maine maryland massachusetts
    michigan minnesota mississippi missouri montana nebraska nevada hampshire jersey mexico york
    carolina dakota ohio oklahoma oregon pennsylvania rhode tennessee texas utah vermont
    virginia washington wisconsin wyoming columbia ontario quebec alberta manitoba
    saskatchewan nova scotia brunswick newfoundland yukon

    amsterdam athens atlanta auckland austin baltimore bangkok barcelona beijing berlin bogota
    boston brisbane brussels budapest buenos aires cairo calgary cape town chicago copenhagen
    dallas delhi denver detroit dubai dublin edinburgh frankfurt geneva glasgow hamburg hanoi
    helsinki hong kong honolulu houston istanbul jakarta jerusalem johannesburg kyiv kiev lagos
    lima lisbon london los angeles lyon madrid manchester manila melbourne miami milan montreal
    moscow mumbai munich nairobi nashville new orleans oakland osaka oslo ottawa paris perth
    philadelphia phoenix pittsburgh portland prague reno rio rome san francisco diego jose
    santiago sao paulo seattle seoul shanghai shenzhen singapore stockholm sydney taipei tokyo
    toronto vancouver vienna warsaw zurich sacramento minneapolis cleveland cincinnati
    charlotte raleigh tampa orlando memphis milwaukee kansas omaha tucson albuquerque
    anchorage boise salt lake vegas fresno honolulu bangalore bengaluru chennai hyderabad
    kolkata pune karachi lahore dhaka riyadh doha tehran baghdad beirut amman casablanca
    tunis accra addis ababa kampala kigali dakar luanda harare lusaka cardiff belfast bristol
    birmingham leeds liverpool oxford cambridge marseille nice bordeaux toulouse cologne
    stuttgart dusseldorf rotterdam antwerp hague bern basel lausanne porto seville valencia
    bilbao naples turin florence venice bologna krakow gdansk bucharest sofia belgrade zagreb
    ljubljana bratislava vilnius riga tallinn reykjavik

    american african asian australian austrian belgian brazilian british canadian chinese
    danish dutch egyptian english european filipino finnish french german greek hispanic indian
    indonesian irish israeli italian japanese korean latino latina mexican nigerian norwegian
    pakistani persian polish portuguese russian scottish spanish swedish swiss thai turkish
    ukrainian vietnamese welsh arab arabic hebrew hindi urdu bengali punjabi tamil mandarin
    cantonese swahili yoruba
    """
)

TECH_TERMS = _words(
    """
    slack zoom google gmail gcal gdrive microsoft msft outlook teams excel word powerpoint office
    sharepoint onedrive onenote github gitlab bitbucket jira confluence trello asana notion
    figma miro salesforce hubspot zendesk intercom dropbox box docusign linkedin twitter
    facebook meta instagram youtube whatsapp signal telegram discord webex skype calendly loom
    airtable smartsheet monday clickup basecamp workday netsuite quickbooks xero stripe paypal
    shopify okta duo lastpass 1password bamboohr gusto greenhouse lever coda obsidian roam
    logseq evernote todoist things bear ulysses scrivener grammarly canva keynote pages numbers
    apple iphone ipad imac macbook macos mac osx windows linux ubuntu debian fedora android ios
    chrome chromium firefox safari edge opera brave aws amazon azure gcp heroku vercel netlify
    cloudflare digitalocean docker kubernetes k8s terraform ansible circleci
    python javascript typescript java kotlin swift golang go rust ruby rails php perl scala
    haskell elixir erlang clojure lua bash zsh shell powershell node nodejs deno bun npm yarn pnpm
    pip pypi conda poetry uv react vue angular svelte nextjs nuxt django flask fastapi express
    spring laravel postgres postgresql mysql mariadb sqlite redis mongodb dynamodb cassandra
    elasticsearch kafka rabbitmq spark hadoop airflow dbt snowflake databricks bigquery redshift
    tableau looker powerbi metabase grafana prometheus datadog sentry pagerduty splunk
    openai anthropic claude chatgpt gpt gemini bard llama mistral copilot cursor vscode vim emacs
    jetbrains pycharm intellij xcode wikipedia wiki stackoverflow reddit medium substack

    markdown md json jsonl yaml yml toml ini csv tsv xml html htm css scss svg png jpg jpeg gif
    webp pdf doc docx xls xlsx ppt pptx odt rtf txt ics ical icalendar vcard vcf webvtt vtt srt
    eml mbox mime utf ascii unicode base64 gzip zip tar http https ftp ssh smtp imap pop dns tcp
    udp ip ipv4 ipv6 url uri urn api apis sdk cli gui ui ux sql nosql etl elt crm erp cms lms
    hris ats sso saml oauth oidc jwt rest graphql grpc rpc webhook webhooks cron yaml regex
    uuid guid md5 sha sha1 sha256 hmac tls ssl vpn lan wan wifi cdn dns llm llms ai ml nlp gpu
    cpu ram ssd hdd os vm vms saas paas iaas b2b b2c dtc readme changelog license makefile
    dockerfile gitignore localhost repo repos monorepo frontmatter wikilink wikilinks backlink
    backlinks kanban scrum sprint epic story
    openid idp idps authenticator gpus wcag vpat stem x-request-id request-id mfa totp
    helvetica arial unsubscribe simplenamespace alliance elevated tech nope

    vcalendar vevent vtimezone valarm vtodo vjournal vfreebusy dtstart dtend dtstamp prodid uid
    rrule exdate rdate tzid tzname tzoffsetfrom tzoffsetto partstat cutype mailto attendee
    organizer calscale gregorian sequence transp opaque transparent tentative confirmed
    cancelled canceled needs-action req-participant opt-participant non-participant accepted
    declined delegated begin end method request cancel reply publish
    note cue voice
    from to cc bcc subject date sender reply-to in-reply-to message-id references mime-version
    content-type content-transfer-encoding content-disposition quoted-printable charset multipart
    boundary attachment inline x-draft x-mailer received return-path dkim spf dmarc

    ceo cfo cto coo cio cmo cpo cro ciso cso chro clo vp svp evp avp gm md hrbp pm pmm tpm em
    swe sre devops devrel qa ux ui ba bd bdr sdr ae am csm cs ops finops secops revops mops
    okr okrs kpi kpis roi sla slas slo slos nda ndas msa sow sows rfp rfps rfi rfq poc pov mvp
    qbr qbrs ebr mbr wbr eod eow eom eoq eoy eta etd fyi asap tbd tbc tba ooo pto wfh rto fte
    ftes pnl p&l arr mrr acv tcv ltv cac nps csat gtm icp tam som capex opex yoy qoq mom
    ytd cagr ebitda gaap ifrs sox gdpr ccpa hipaa pci soc iso pii phi dpa baa dsar
    llc inc ltd corp co plc gmbh ag sa bv pty llp lp nv oy ab as kk

    def class import from return self cls none true false null nil undefined const let var
    function func fn async await lambda yield print printf str string int integer float double
    bool boolean dict list tuple set len range args kwargs init main todo fixme xxx hack noqa
    pragma typing optional union callable iterable iterator generator dataclass enum pathlib
    pytest unittest assert raise except try finally elif else while for break continue pass
    global nonlocal staticmethod classmethod property super object type types schema schemas
    additionalproperties patternproperties propertynames minlength maxlength minitems maxitems
    uniqueitems minproperties maxproperties oneof anyof allof enum const ref defs definitions
    minimum maximum exclusiveminimum exclusivemaximum multipleof datetime iso8601 rfc
    dataset datasets ctrl alt cmd esc fn tab del ins pgup pgdn sigint sigterm sigkill sighup
    sigquit sigusr1 sigusr2 sigpipe sigchld tmpdir tmp temp env stdin stdout stderr pythonpath
    yyyy yy mm dd hh ss tz tld tlds dumper loader safedumper safeloader
    """
)

#: Exception and constant names from Python's builtins ("ValueError", "None", ...).
PYTHON_NAMES = frozenset(n.lower() for n in dir(builtins) if n[:1].isupper())

FIRST_NAMES = _words(
    """
    aaron abby abigail ada adam adrian ahmed aidan aiden aisha alan albert alex alexander
    alexandra alexis alfred ali alice alicia alison allison alyssa amanda amber amelia amir amit
    amy ana anand andre andrea andrew andy angela angelica anil anita ann anna anne annie anthony
    antonio april arjun arthur arun ashley audrey austin ava barbara barry beatrice ben benjamin
    bernard beth betty beverly bill billy blake bob bobby bonnie brad bradley brandon brenda
    brett brian brittany brooke bruce bryan caleb cameron camila carl carla carlos carmen carol
    caroline carolyn carrie casey catherine charles charlie charlotte chelsea chen cheryl chloe
    chris christian christina christine christopher cindy claire clara claudia colin connor
    courtney craig crystal cynthia daisy dale dan dana daniel danielle danny darren dave david
    dawn dean debbie deborah debra denise dennis derek diana diane diego dmitri dominic don donald
    donna doris dorothy doug douglas dylan eddie edward elaine eleanor elena eli elijah elizabeth
    ella ellen emily emma eric erica erik erin ethan eugene eva evan evelyn faith fatima felix
    fernando fiona frances francesca francis frank fred gabriel gabriela gail gary gavin george
    gerald gina giovanni glen glenn gloria grace graham grant greg gregory hannah hans harold
    harper harry hassan hazel heather heidi helen henry holly howard hugh hugo ian irene isaac
    isabel isabella ivan jack jackie jacob jacqueline jade jake james jamie jan jane janet janice
    jared jason javier jay jean jeff jeffrey jen jenna jennifer jeremy jerry jesse jessica jill
    jim jimmy jin joan joanna joe joel john johnny jon jonathan jordan jorge jose joseph josh
    joshua joy joyce juan judith judy julia julian julie justin karen karl kate katherine kathleen
    kathryn kathy katie kayla keith kelly ken kenji kenneth kevin kim kimberly kyle lana lara
    larry laura lauren lawrence leah lee leo leon leslie liam lily linda lisa liz logan lori
    louis louise lucas lucia lucy luis luke lynn madison maggie mandy manuel marco marcus margaret
    maria marie marilyn mario mark martha martin marvin mary mason matt matthew maurice max maya
    megan mei melanie melissa mia michael michelle miguel mike mila miles min mohammed molly
    monica morgan muhammad nadia nancy naomi natalie nathan neha neil nick nicholas nicole nina
    noah nora olga oliver olivia omar oscar owen pamela patricia patrick paul paula pedro peggy
    peter phil philip phillip phyllis pierre priya rachel rafael rahul raj ralph ramon randy ravi
    ray raymond rebecca regina rhonda ricardo richard rick riley rita rob robert roberto robin
    rodney roger ron ronald rosa rose ross roy ruby russell ruth ryan sabrina sally sam samantha
    samuel sandra sara sarah scott sean sergei seth shannon sharon shawn sheila shirley simon
    sofia sophia sophie stacy stanley stephanie stephen steve steven sue susan suzanne sylvia
    tammy tanya tara ted teresa terry theresa thomas tiffany tim timothy tina todd tom tommy tony
    tracy travis trevor troy tyler valerie vanessa veronica victor victoria vincent virginia
    vivian wanda wayne wei wendy william willie xavier yan yolanda yuki yusuf zach zachary zoe

    abdul abdullah ahmad aditi aditya akira alejandro ali amina anjali ankit aryan ayesha bilal
    carlos chiara deepak dong emre fatma fang feng gregor guo hamza hao haruto hiroshi hui ibrahim
    jiho jun kaito karim kavya khalid kofi kwame lakshmi li ling lukas mahmoud malik manoj maryam
    mateo matteo mehmet ming minh mustafa naveen nikhil ning omar pooja rajesh rohan sakura
    sanjay santiago satoshi shreya sneha sunil suresh takashi tao thanh valentina vikram xin
    yang yasmin ying yong yu yusuf zainab zhen
    """
)

SURNAMES = _words(
    """
    abbott acosta adams aguilar ahmed ali allen alvarez anderson andrews armstrong arnold
    austin bailey baker baldwin banks barber barker barnes barnett barrett barton bates beck
    becker bell bennett benson berry bishop black blair boyd bradley brady brewer brooks brown
    bryant burke burns burton bush butler byrd caldwell campbell cannon carlson carpenter carr
    carroll carter castillo castro chambers chan chang chapman chavez chen choi christensen clark
    clarke cohen cole coleman collins cook cooper cortez cox craig crawford cross cruz cummings
    cunningham curtis daniel daniels davidson davis dawson day dean delgado diaz dixon dominguez
    douglas doyle duncan dunn edwards elliott ellis erickson espinoza estrada evans farmer
    ferguson fernandez fields figueroa fischer fisher fitzgerald fleming fletcher flores flynn
    ford foster fowler fox francis franklin frazier freeman fuller garcia gardner garrett garza
    george gibson gilbert gomez gonzales gonzalez goodman goodwin gordon graham grant graves gray
    green greene gregory griffin gross guerrero gutierrez guzman hale hall hamilton hammond
    hansen hanson hardy harmon harper harrington harris harrison hart harvey hawkins hayes
    henderson henry hernandez herrera hicks higgins hill hines hoffman holland holmes holt
    hopkins horton howard howell huang hudson hughes hunt hunter ingram jackson jacobs james
    jenkins jennings jensen jimenez johnson johnston jones jordan joseph kaur keller kelley kelly
    kennedy khan kim king klein knight kramer lambert lane larson lawrence lawson le lee leonard
    lewis li lin little liu logan long lopez love lowe lucas luna lynch mack maldonado malone mann
    manning marquez marsh marshall martin martinez mason matthews maxwell may mccarthy mccoy
    mcdaniel mcdonald mcgee mckinney meyer miles miller mills miranda mitchell molina montgomery
    moore morales moreno morgan morris morrison moss mueller munoz murphy murray myers nelson
    newman newton nguyen nichols norman norris nunez obrien oconnor oliver olson ortega ortiz
    owen owens padilla page palmer park parker parks patel patterson patton paul payne pearson
    pena perez perkins perry peters peterson pham phillips pierce porter powell powers price
    quinn ramirez ramos ramsey ray reed reese reeves reid reyes reynolds rhodes rice richards
    richardson riley rios rivera robbins roberts robertson robinson rodgers rodriguez rogers
    rojas roman romero rose ross rowe ruiz russell ryan salazar sanchez sanders sandoval santiago
    santos saunders schmidt schneider schultz schwartz scott shaw shelton sherman silva simmons
    simon simpson sims singh smith snyder soto spencer stanley steele stephens stevens stewart
    stone sullivan sutton swanson tan tang tate taylor terry thomas thompson thornton torres tran
    tucker turner valdez vargas vasquez vaughn vega velasquez velez wagner walker wallace walsh
    walters wang ward warner warren washington watkins watson watts weaver webb weber welch wells
    west wheeler white wilkins williams williamson willis wilson wise wolf wolfe wong wood woods
    wright wu yang yates young zhang zhao zhou zimmerman

    agarwal ahmad akhtar almeida andersson bakker banerjee bauer bianchi bose cai cao chakraborty
    chaudhry cheng chopra chowdhury colombo costa dang das deng desai ding dong dubois durand
    eriksson esposito ferrari feng gao gupta han hassan hoang hossain hu hussain ibrahim islam
    ito iyer jain jansen jiang johansson joshi kapoor karlsson kato kobayashi kowalski kumar
    kuznetsov larsen laurent lefebvre leroy liang lu luo malik ma mehta meijer moreau muller
    nakamura nair nilsson nowak olsen oliveira pan pedersen peng pereira petit popov qureshi
    rahman rao reddy ricci rodrigues romano rossi russo saito sato sharma shen sinha smirnov song
    souza su sun suzuki takahashi tanaka tian van visser vo vu wagner watanabe xiao xie xu yadav
    yamamoto yao ye yuan zeng zheng zhong zhu
    """
)

#: Every set whose members the scanner never reports as proper nouns.
NEVER_REPORTED = (
    COMMON_WORDS | MONTHS | WEEKDAYS | CALENDAR_WORDS | PLACES | TECH_TERMS | PYTHON_NAMES
)

#: Names that downgrade a single-word proper-noun finding to "low".
COMMON_NAMES = FIRST_NAMES | SURNAMES
