"""Hand-authored synthetic case library.

Owner: Engineer 1.

Every person, company and protocol here is fictional. Cases are deliberately
stylised so that each demonstrates a specific procedural or game-theoretic
phenomenon (see the ``tags`` field).
"""

from __future__ import annotations

from typing import Any

from courtroom.contracts import (
    CaseFile,
    CaseType,
    EvidenceItem,
    EvidenceKind,
    LegalElement,
    Side,
    StandardOfProof,
    Witness,
)

P, D = Side.PROSECUTION, Side.DEFENSE
K = EvidenceKind


def ev(
    id: str, owner: Side, kind: EvidenceKind, title: str, support: dict[str, float], reliability: float, **kw: Any
) -> EvidenceItem:
    return EvidenceItem(
        id=id,
        owner=owner,
        kind=kind,
        title=title,
        description=kw.pop("description", title),
        support=support,
        reliability=reliability,
        fact_id=kw.pop("fact", id),
        **kw,
    )


# ============================================================================ 1. Flagship


HELIX = CaseFile(
    id="helix-espionage",
    title="State v. Adrian Vance — Helix Dynamics Trade-Secret Exfiltration",
    synopsis=(
        "A senior engineer at Helix Dynamics is accused of copying the 'Tessellate' chip "
        "floor-plan to a personal cloud drive at 02:14 and selling it to competitor Quorvex. "
        "The defense says his credentials were phished and he was home all night."
    ),
    case_type=CaseType.CRIMINAL,
    standard=StandardOfProof.BEYOND_REASONABLE_DOUBT,
    charge="Theft of trade secrets (synthetic statute §18-TS)",
    elements=(
        LegalElement(
            id="access", name="Unauthorised access", description="Defendant personally accessed the protected repository."
        ),
        LegalElement(id="exfiltration", name="Exfiltration", description="Protected data left Helix control."),
        LegalElement(
            id="intent", name="Intent to benefit a competitor", description="Defendant acted to benefit Quorvex or himself."
        ),
    ),
    witnesses=(
        Witness(
            id="W-NANDA",
            name="Priya Nandakumar",
            role="Co-worker",
            credibility=0.75,
            bias_note="Passed over for the same promotion.",
        ),
        Witness(id="W-OKAFOR", name="Det. Samuel Okafor", role="Investigating detective", credibility=0.85),
        Witness(
            id="W-VANCE-SPOUSE",
            name="Mira Vance",
            role="Defendant's spouse",
            credibility=0.55,
            bias_note="Spouse of the accused.",
        ),
        Witness(id="W-HR", name="Tom Reyes", role="HR manager", credibility=0.7),
        Witness(id="W-NEIGH", name="Dana Whitfield", role="Neighbour", credibility=0.8),
    ),
    evidence=(
        # --- Prosecution
        ev(
            "P-VPN",
            P,
            K.DIGITAL_LOG,
            "VPN log: Vance credentials connect at 02:09",
            {"access": 0.8},
            0.9,
            contradicts=("D-ROUTER",),
        ),
        ev(
            "P-BADGE",
            P,
            K.DOCUMENT,
            "Badge reader: Vance badge used at Lab B, 02:02",
            {"access": 0.6},
            0.85,
            contradicts=("D-SPOUSE",),
        ),
        ev(
            "P-DLP",
            P,
            K.DIGITAL_LOG,
            "DLP alert: 4.2 GB upload to personal cloud drive",
            {"exfiltration": 0.9},
            0.8,
            authenticated=False,
            description="Export lacks the SIEM hash certificate.",
        ),
        ev(
            "P-LAPTOP",
            P,
            K.PHYSICAL,
            "Forensic image of seized laptop shows Tessellate files",
            {"exfiltration": 0.8, "intent": 0.3},
            0.9,
            lawfully_obtained=False,
            description="Search executed one day after the warrant expired.",
        ),
        ev(
            "P-EXPERT",
            P,
            K.EXPERT,
            "Dr. Lena Marsh: upload volume matches Tessellate archive",
            {"exfiltration": 0.6, "access": 0.3},
            0.85,
        ),
        ev(
            "P-NANDA",
            P,
            K.TESTIMONY,
            "Nandakumar: 'He said Quorvex would make him rich'",
            {"intent": 0.7},
            0.8,
            witness_id="W-NANDA",
        ),
        ev(
            "P-TIP",
            P,
            K.TESTIMONY,
            "Okafor relays informant: Vance shopped the design",
            {"intent": 0.6},
            0.8,
            witness_id="W-OKAFOR",
            hearsay=True,
        ),
        ev(
            "P-EMAILS",
            P,
            K.DOCUMENT,
            "Quorvex recruiter emails promising a 'signing bonus for IP'",
            {"intent": 0.65},
            0.9,
            disclosed=False,
        ),
        ev("P-CRYPTO", P, K.FINANCIAL_RECORD, "USD 40k stablecoin deposit 12 days later", {"intent": 0.5}, 0.75),
        ev(
            "P-CCTV",
            P,
            K.PHYSICAL,
            "Garage CCTV: Vance's car enters at 01:50",
            {"access": 0.5},
            0.8,
            contradicts=("D-SPOUSE", "D-ROUTER"),
        ),
        # --- Defense
        ev(
            "D-SPOUSE",
            D,
            K.TESTIMONY,
            "Mira Vance: 'Adrian was home asleep all night'",
            {"access": -0.7},
            0.8,
            witness_id="W-VANCE-SPOUSE",
        ),
        ev("D-ROUTER", D, K.DIGITAL_LOG, "Home router: Vance's phone and laptop online at 02:10", {"access": -0.6}, 0.7),
        ev("D-PHISH", D, K.DOCUMENT, "IT memo: service credentials compromised in March phishing wave", {"access": -0.5}, 0.8),
        ev(
            "D-DLPEXPERT", D, K.EXPERT, "Prof. Ian Cho: this DLP rule has a 30% false-positive rate", {"exfiltration": -0.5}, 0.75
        ),
        ev(
            "D-HR",
            D,
            K.TESTIMONY,
            "Reyes: upload was probably an approved personal backup",
            {"exfiltration": -0.4, "intent": -0.3},
            0.7,
            witness_id="W-HR",
            personal_knowledge=False,
        ),
        ev(
            "D-REVIEW",
            D,
            K.DOCUMENT,
            "Nandakumar's grievance filing against Vance",
            {"intent": -0.1},
            0.9,
            impeaches=("W-NANDA",),
        ),
        ev(
            "D-CHARACTER",
            D,
            K.TESTIMONY,
            "Neighbour: 'Adrian mows his lawn every Sunday'",
            {"intent": -0.02},
            0.9,
            witness_id="W-NEIGH",
        ),
    ),
    budget=12.0,
    max_primary_turns=10,
    perception_accuracy=0.65,
    tags=("flagship", "balanced", "contradictions", "impeachment", "exclusionary-rule"),
)


# ============================================================================ 2. DeFi exploit


AURORA = CaseFile(
    id="aurora-defi",
    title="People v. 'nyx.eth' — Aurora Protocol Flash-Loan Exploit",
    synopsis=(
        "USD 31M was drained from the Aurora lending protocol via an oracle-manipulation flash loan. "
        "Prosecution ties the exploit wallet to the defendant; the defense claims a white-hat rescue "
        "under Aurora's published bug-bounty policy."
    ),
    case_type=CaseType.CRIMINAL,
    standard=StandardOfProof.BEYOND_REASONABLE_DOUBT,
    charge="Computer fraud (synthetic statute §10-CF)",
    elements=(
        LegalElement(id="control", name="Wallet control", description="Defendant controlled the exploit wallet."),
        LegalElement(id="execution", name="Exploit execution", description="The wallet executed the draining transactions."),
        LegalElement(
            id="fraud_intent", name="Intent to defraud", description="Defendant intended to permanently deprive depositors."
        ),
    ),
    witnesses=(
        Witness(id="W-CHAIN", name="Rosa Ibarra", role="Blockchain analyst", credibility=0.8),
        Witness(
            id="W-DEV", name="Kofi Mensah", role="Aurora core developer", credibility=0.65, bias_note="Lost his own deposits."
        ),
        Witness(id="W-BOUNTY", name="Lin Zhao", role="Bug-bounty coordinator", credibility=0.75),
    ),
    evidence=(
        ev("P-TRACE", P, K.EXPERT, "Ibarra: funding hop from defendant's KYC'd exchange account", {"control": 0.8}, 0.85),
        ev(
            "P-TXS",
            P,
            K.DIGITAL_LOG,
            "On-chain transactions 0xa1..0xa9 draining the pool",
            {"execution": 0.95},
            0.99,
            fact="onchain",
        ),
        ev(
            "P-TXS-DUP",
            P,
            K.DIGITAL_LOG,
            "Block-explorer printout of the same transactions",
            {"execution": 0.9},
            0.95,
            fact="onchain",
        ),
        ev(
            "P-SEED",
            P,
            K.PHYSICAL,
            "Seed phrase found on paper in defendant's flat",
            {"control": 0.95},
            0.95,
            lawfully_obtained=False,
            description="Warrantless entry; no exigency.",
        ),
        ev(
            "P-KYC",
            P,
            K.FINANCIAL_RECORD,
            "Exchange KYC file linking the funding account",
            {"control": 0.6},
            0.9,
            disclosed=False,
        ),
        ev("P-MIXER", P, K.DIGITAL_LOG, "USD 9M routed through a privacy mixer", {"fraud_intent": 0.7}, 0.85),
        ev(
            "P-DEV",
            P,
            K.TESTIMONY,
            "Mensah: 'no white-hat ever moved funds this way'",
            {"fraud_intent": 0.5},
            0.7,
            witness_id="W-DEV",
            personal_knowledge=False,
        ),
        ev("P-CHAT", P, K.DOCUMENT, "Telegram message: 'time to retire lol'", {"fraud_intent": 0.55}, 0.6, authenticated=False),
        ev(
            "D-BOUNTY",
            D,
            K.DOCUMENT,
            "Aurora bug-bounty policy: 10% finder's fee on returned funds",
            {"fraud_intent": -0.6},
            0.95,
        ),
        ev(
            "D-RETURN",
            D,
            K.DIGITAL_LOG,
            "USD 22M returned to Aurora multisig 48h later",
            {"fraud_intent": -0.75},
            0.95,
            contradicts=("P-MIXER",),
        ),
        ev(
            "D-ZHAO",
            D,
            K.TESTIMONY,
            "Zhao: defendant contacted bounty desk within 2 hours",
            {"fraud_intent": -0.5},
            0.8,
            witness_id="W-BOUNTY",
        ),
        ev(
            "D-SHARED",
            D,
            K.EXPERT,
            "Wallet-clustering heuristic has 25% error rate",
            {"control": -0.45},
            0.7,
            contradicts=("P-TRACE",),
        ),
        ev(
            "D-DEVBIAS",
            D,
            K.FINANCIAL_RECORD,
            "Mensah's own losses in the exploit",
            {"fraud_intent": -0.05},
            0.9,
            impeaches=("W-DEV",),
        ),
    ),
    budget=11.0,
    max_primary_turns=7,
    tags=("defi", "exclusionary-rule", "cumulative-evidence", "white-hat-defense"),
)


# ============================================================================ 3. Civil AV liability


KESTREL = CaseFile(
    id="kestrel-av",
    title="Halvorsen v. Kestrel Mobility — AV-7 Crosswalk Collision",
    synopsis=(
        "A Kestrel AV-7 robotaxi struck a cyclist in a crosswalk. Plaintiff alleges a perception-stack "
        "defect; Kestrel says the cyclist ran a red light. Two eyewitnesses give mutually exclusive "
        "accounts of the signal."
    ),
    case_type=CaseType.CIVIL,
    standard=StandardOfProof.PREPONDERANCE,
    charge="Product liability: defective design (synthetic tort)",
    elements=(
        LegalElement(id="defect", name="Design defect", description="The perception stack was defectively designed."),
        LegalElement(id="causation", name="Causation", description="The defect caused the collision."),
        LegalElement(id="damages", name="Damages", description="Plaintiff suffered compensable harm."),
    ),
    witnesses=(
        Witness(id="W-EYE1", name="Grace Obi", role="Pedestrian eyewitness", credibility=0.7),
        Witness(id="W-EYE2", name="Martin Lund", role="Driver of adjacent car", credibility=0.7),
        Witness(
            id="W-ENG", name="Dr. Aiko Tan", role="Former Kestrel engineer", credibility=0.6, bias_note="Terminated by Kestrel."
        ),
        Witness(id="W-MED", name="Dr. Ruth Adeyemi", role="Treating physician", credibility=0.9),
    ),
    evidence=(
        ev(
            "P-EYE1",
            P,
            K.TESTIMONY,
            "Obi: 'The walk signal was green for the cyclist'",
            {"causation": 0.6},
            0.8,
            witness_id="W-EYE1",
            contradicts=("D-EYE2",),
        ),
        ev(
            "P-BUGS",
            P,
            K.DOCUMENT,
            "Internal ticket: 'bicycle class dropped at dusk' marked WONTFIX",
            {"defect": 0.8},
            0.85,
            disclosed=False,
        ),
        ev("P-TAN", P, K.TESTIMONY, "Tan: 'We shipped knowing dusk recall was 71%'", {"defect": 0.65}, 0.75, witness_id="W-ENG"),
        ev("P-RECON", P, K.EXPERT, "Crash reconstruction: braking began 0.9s late", {"causation": 0.55, "defect": 0.3}, 0.8),
        ev(
            "P-MED",
            P,
            K.TESTIMONY,
            "Adeyemi: fractured pelvis, 14 weeks rehabilitation",
            {"damages": 0.9},
            0.95,
            witness_id="W-MED",
        ),
        ev("P-BILLS", P, K.FINANCIAL_RECORD, "Medical bills USD 186k", {"damages": 0.7}, 0.95),
        ev(
            "P-FORUM",
            P,
            K.DOCUMENT,
            "Anonymous forum post: 'AV-7 can't see bikes'",
            {"defect": 0.4},
            0.3,
            hearsay=True,
            authenticated=False,
        ),
        ev(
            "D-EYE2",
            D,
            K.TESTIMONY,
            "Lund: 'The cyclist had a red light'",
            {"causation": -0.6},
            0.8,
            witness_id="W-EYE2",
            contradicts=("P-EYE1",),
        ),
        ev(
            "D-TELEM",
            D,
            K.DIGITAL_LOG,
            "AV-7 telemetry: cyclist detected 1.6s before impact",
            {"defect": -0.4, "causation": -0.3},
            0.85,
            contradicts=("P-RECON",),
        ),
        ev("D-NHTSA", D, K.DOCUMENT, "Synthetic regulator audit: perception stack compliant", {"defect": -0.3}, 0.7),
        ev(
            "D-TERM", D, K.DOCUMENT, "Tan's termination record for data mishandling", {"defect": -0.05}, 0.9, impeaches=("W-ENG",)
        ),
        ev("D-HELMET", D, K.PHYSICAL, "Cyclist not wearing helmet", {"damages": -0.2}, 0.9),
    ),
    budget=10.0,
    max_primary_turns=7,
    perception_accuracy=0.65,
    tags=("civil", "preponderance", "mutually-exclusive-witnesses"),
)


# ============================================================================ 4-7. Pathological edge cases


EMPTY = CaseFile(
    id="edge-empty-docket",
    title="State v. Doe — The Empty Docket",
    synopsis="The prosecution filed charges but has no evidence at all. Must end in a directed acquittal without errors.",
    case_type=CaseType.CRIMINAL,
    standard=StandardOfProof.BEYOND_REASONABLE_DOUBT,
    charge="Unspecified cyber offence",
    elements=(
        LegalElement(id="act", name="Actus reus", description="The act occurred."),
        LegalElement(id="identity", name="Identity", description="Defendant did it."),
    ),
    tags=("edge-case", "zero-evidence"),
)

STALEMATE = CaseFile(
    id="edge-mutual-exclusion",
    title="Orbital Freight v. Lark — Mutually Exclusive Testimony",
    synopsis=(
        "Two equally credible witnesses give flatly contradictory accounts of who issued a rogue drone "
        "command, with nothing else. Tests symmetric contradiction resolution."
    ),
    case_type=CaseType.CIVIL,
    standard=StandardOfProof.PREPONDERANCE,
    charge="Negligent operation of an autonomous drone fleet",
    elements=(LegalElement(id="command", name="Command issued", description="Defendant issued the rogue command."),),
    witnesses=(
        Witness(id="W-A", name="Operator A", role="Shift operator", credibility=0.8),
        Witness(id="W-B", name="Operator B", role="Shift operator", credibility=0.8),
    ),
    evidence=(
        ev(
            "P-A",
            P,
            K.TESTIMONY,
            "Operator A: 'Lark typed the command'",
            {"command": 0.8},
            0.8,
            witness_id="W-A",
            contradicts=("D-B",),
        ),
        ev(
            "D-B",
            D,
            K.TESTIMONY,
            "Operator B: 'Lark was on break; I was at that console'",
            {"command": -0.8},
            0.8,
            witness_id="W-B",
            contradicts=("P-A",),
        ),
    ),
    budget=6.0,
    max_primary_turns=4,
    tags=("edge-case", "contradiction", "symmetric"),
)

TAINTED = CaseFile(
    id="edge-poisoned-tree",
    title="State v. Kaur — Fruit of the Poisonous Tree",
    synopsis="Every prosecution exhibit is defective. An objecting defense wins; a passive defense can still lose.",
    case_type=CaseType.CRIMINAL,
    standard=StandardOfProof.BEYOND_REASONABLE_DOUBT,
    charge="Ransomware deployment (synthetic statute §7-RW)",
    elements=(
        LegalElement(id="deployment", name="Deployment", description="Defendant deployed the payload."),
        LegalElement(id="extortion", name="Extortion", description="Defendant demanded ransom."),
    ),
    witnesses=(Witness(id="W-INF", name="Paid informant", role="Informant", credibility=0.5),),
    evidence=(
        ev(
            "P-WIRE",
            P,
            K.DIGITAL_LOG,
            "Warrantless wiretap: payload discussion",
            {"deployment": 0.9},
            0.9,
            lawfully_obtained=False,
        ),
        ev(
            "P-DRIVE",
            P,
            K.PHYSICAL,
            "Drive seized in the same illegal search",
            {"deployment": 0.8, "extortion": 0.4},
            0.9,
            lawfully_obtained=False,
        ),
        ev("P-NOTE", P, K.DOCUMENT, "Ransom note, chain of custody broken", {"extortion": 0.85}, 0.85, authenticated=False),
        ev(
            "P-INF",
            P,
            K.TESTIMONY,
            "Informant: 'someone told me Kaur did it'",
            {"deployment": 0.5, "extortion": 0.5},
            0.6,
            witness_id="W-INF",
            hearsay=True,
        ),
        ev(
            "P-WALLET",
            P,
            K.FINANCIAL_RECORD,
            "Ransom wallet records disclosed on day of trial",
            {"extortion": 0.7},
            0.9,
            disclosed=False,
        ),
    ),
    budget=10.0,
    max_primary_turns=6,
    tags=("edge-case", "all-inadmissible", "objection-value"),
)

DEFENSE_ONLY = CaseFile(
    id="edge-defense-only",
    title="State v. Park — Prosecution Brings Only Exculpatory Material",
    synopsis="The only evidence in the file helps the defense. DV-2 must fire even if the defense never moves.",
    case_type=CaseType.CRIMINAL,
    standard=StandardOfProof.BEYOND_REASONABLE_DOUBT,
    charge="Insider trading (synthetic statute §3-IT)",
    elements=(
        LegalElement(id="trade", name="Trade on MNPI", description="Defendant traded on material non-public information."),
    ),
    evidence=(
        ev("D-ALIBI", D, K.DOCUMENT, "Trade was scheduled under a 10b5-1-style plan", {"trade": -0.8}, 0.95),
        ev("P-WEAK", P, K.DOCUMENT, "Calendar entry unrelated to the trade", {"trade": -0.1}, 0.9),
    ),
    tags=("edge-case", "no-inculpatory-evidence"),
)


# ============================================================================ 8-10. Everyday cases (plain language)


COOKIE = CaseFile(
    id="cookie-jar",
    title="School v. Sam — The Missing Cookies",
    synopsis=(
        "A whole jar of cookies vanished from the school kitchen during lunch. A classmate says she saw "
        "Sam near the kitchen with crumbs on his shirt. Sam says he was in the library the whole time."
    ),
    case_type=CaseType.CRIMINAL,
    standard=StandardOfProof.BEYOND_REASONABLE_DOUBT,
    charge="Taking the cookies without asking",
    elements=(
        LegalElement(id="there", name="Sam was in the kitchen", description="Sam was in the kitchen when the cookies went missing."),
        LegalElement(id="took", name="Sam took the cookies", description="Sam is the one who took the cookies."),
    ),
    witnesses=(
        Witness(id="W-MAYA", name="Maya", role="Classmate", credibility=0.75, bias_note="Sam beat her in the spelling contest."),
        Witness(id="W-LIB", name="Mr. Ortiz", role="Librarian", credibility=0.9),
        Witness(id="W-COOK", name="Mrs. Bell", role="School cook", credibility=0.85),
    ),
    evidence=(
        ev("P-MAYA", P, K.TESTIMONY, "Maya: 'I saw Sam walk into the kitchen'", {"there": 0.7}, 0.8, witness_id="W-MAYA",
           contradicts=("D-LIBRARIAN",)),
        ev("P-CRUMBS", P, K.PHYSICAL, "Cookie crumbs found on Sam's shirt", {"took": 0.8}, 0.8),
        ev("P-CAMERA", P, K.DIGITAL_LOG, "Hallway camera: a kid in a red jacket near the kitchen", {"there": 0.8}, 0.85),
        ev("P-RUMOR", P, K.TESTIMONY, "Mrs. Bell: 'A student told me Sam did it'", {"took": 0.5}, 0.7, witness_id="W-COOK",
           hearsay=True),
        ev("D-LIBRARIAN", D, K.TESTIMONY, "Mr. Ortiz: 'Sam was reading in the library all lunch'", {"there": -0.7}, 0.9,
           witness_id="W-LIB", contradicts=("P-MAYA",)),
        ev("D-SNACK", D, K.DOCUMENT, "Lunch note: Sam's mom packed cookies in his own lunchbox", {"took": -0.5}, 0.85),
        ev("D-CONTEST", D, K.DOCUMENT, "Spelling contest results: Sam beat Maya last week", {"took": -0.05}, 0.95,
           impeaches=("W-MAYA",)),
    ),
    budget=8.0,
    max_primary_turns=5,
    tags=("everyday", "simple", "alibi"),
)

BIKE = CaseFile(
    id="broken-bike",
    title="Lee v. Patel — The Broken Bike",
    synopsis=(
        "Ana lent her new bike to her neighbour Raj for one afternoon. It came back with a bent wheel. "
        "Ana wants Raj to pay for the repair. Raj says the wheel was already wobbly when he got it."
    ),
    case_type=CaseType.CIVIL,
    standard=StandardOfProof.PREPONDERANCE,
    charge="Not paying for damage to a borrowed bike",
    elements=(
        LegalElement(id="damaged", name="Raj damaged the bike", description="The wheel got bent while Raj had the bike."),
        LegalElement(id="cost", name="The repair costs money", description="Ana had to pay to fix the wheel."),
    ),
    witnesses=(
        Witness(id="W-SHOP", name="Kim", role="Bike shop mechanic", credibility=0.9),
        Witness(id="W-FRIEND", name="Leo", role="Raj's friend", credibility=0.6, bias_note="Best friends with Raj."),
    ),
    evidence=(
        ev("P-PHOTO", P, K.PHYSICAL, "Photo of the bike with a straight wheel, taken the morning Raj borrowed it",
           {"damaged": 0.4}, 0.75, contradicts=("D-WOBBLE",)),
        ev("P-TEXT", P, K.DOCUMENT, "Text from Raj: 'Sorry, I hit a curb'", {"damaged": 0.8}, 0.8, authenticated=False),
        ev("P-RECEIPT", P, K.FINANCIAL_RECORD, "Bike shop receipt: $90 for a new wheel", {"cost": 0.9}, 0.95),
        ev("P-MECHANIC", P, K.EXPERT, "Kim: 'This bend comes from hitting something hard'", {"damaged": 0.3}, 0.8),
        ev("D-WOBBLE", D, K.TESTIMONY, "Leo: 'The wheel was already wobbly when Raj picked it up'", {"damaged": -0.6}, 0.7,
           witness_id="W-FRIEND", contradicts=("P-PHOTO",)),
        ev("D-OLD", D, K.DOCUMENT, "Bike sale ad: 'Used bike, small wheel issue'", {"damaged": -0.3}, 0.6, disclosed=False),
        ev("D-FRIENDSHIP", D, K.DOCUMENT, "Photo of Leo and Raj on holiday together", {"damaged": -0.02}, 0.95,
           impeaches=("W-FRIEND",)),
    ),
    budget=8.0,
    max_primary_turns=5,
    tags=("everyday", "simple", "civil"),
)

DOG = CaseFile(
    id="garden-dog",
    title="Neighbours v. Rex's Owner — The Dug-Up Garden",
    synopsis=(
        "Someone dug up Mrs. Green's tomato garden overnight. She thinks it was Rex, the dog next door. "
        "Rex's owner says the fence was closed and Rex never left the yard."
    ),
    case_type=CaseType.CIVIL,
    standard=StandardOfProof.PREPONDERANCE,
    charge="Letting a dog ruin a neighbour's garden",
    elements=(
        LegalElement(id="dog", name="Rex dug the garden", description="Rex is the one who dug up the tomatoes."),
        LegalElement(id="careless", name="The owner was careless", description="The owner let Rex get out."),
    ),
    witnesses=(
        Witness(id="W-GREEN", name="Mrs. Green", role="Garden owner", credibility=0.7, bias_note="Has complained about Rex before."),
        Witness(id="W-VET", name="Dr. Fox", role="Vet", credibility=0.9),
    ),
    evidence=(
        ev("P-PAWS", P, K.PHYSICAL, "Muddy paw prints leading from the garden to the fence", {"dog": 0.8}, 0.85),
        ev("P-GATE", P, K.PHYSICAL, "Photo of the fence gate left open in the morning", {"careless": 0.7}, 0.8,
           contradicts=("D-LOCK",)),
        ev("P-GREEN", P, K.TESTIMONY, "Mrs. Green: 'I heard barking in my garden at night'", {"dog": 0.5}, 0.75,
           witness_id="W-GREEN"),
        ev("P-RACCOON", P, K.TESTIMONY, "Mrs. Green: 'My cousin says Rex always digs'", {"dog": 0.4}, 0.5,
           witness_id="W-GREEN", hearsay=True),
        ev("D-LOCK", D, K.DIGITAL_LOG, "Smart lock log: gate locked from 9 pm to 7 am", {"careless": -0.7}, 0.85,
           contradicts=("P-GATE",)),
        ev("D-VET", D, K.EXPERT, "Dr. Fox: 'These prints are too small for Rex. They look like a raccoon'", {"dog": -0.6}, 0.85),
        ev("D-COMPLAINTS", D, K.DOCUMENT, "Mrs. Green's five past complaints about Rex", {"dog": -0.05}, 0.9,
           impeaches=("W-GREEN",)),
    ),
    budget=8.0,
    max_primary_turns=5,
    tags=("everyday", "simple", "civil", "expert"),
)


CASES: dict[str, CaseFile] = {
    c.id: c for c in (COOKIE, BIKE, DOG, HELIX, AURORA, KESTREL, EMPTY, STALEMATE, TAINTED, DEFENSE_ONLY)
}


def get_case(case_id: str) -> CaseFile:
    try:
        return CASES[case_id]
    except KeyError:
        raise KeyError(f"unknown case {case_id!r}; available: {sorted(CASES)}") from None
