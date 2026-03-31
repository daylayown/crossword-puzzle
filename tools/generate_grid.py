#!/usr/bin/env python3
"""Find a valid 5x5 mini crossword grid with black squares.

Uses a standard NYT Mini-style layout with rotationally symmetric black squares.
Across and down answers are naturally different because black squares break symmetry.
"""

import json
import random
import sys
from pathlib import Path

# Word lists by length
WORDS_5 = [
    "ABOUT", "ABOVE", "ABUSE", "ACTED", "ADAPT", "ADDED", "ADMIT", "ADOPT",
    "AGENT", "AGREE", "AHEAD", "AIMED", "ALARM", "ALBUM", "ALERT", "ALIEN",
    "ALIGN", "ALIKE", "ALIVE", "ALLOW", "ALONE", "ALONG", "ALTER", "AMAZE",
    "AMONG", "AMPLE", "ANGEL", "ANGER", "ANGLE", "APART", "ARENA", "ARGUE",
    "ARISE", "ARMED", "ARMOR", "ASIDE", "ASSET", "AUDIT", "AVOID", "AWARD",
    "AWARE", "BASIC", "BASIN", "BASIS", "BEGAN", "BEGIN", "BEING", "BELOW",
    "BENCH", "BIRTH", "BLACK", "BLADE", "BLAME", "BLAND", "BLANK", "BLAST",
    "BLAZE", "BLEED", "BLEND", "BLESS", "BLIND", "BLOCK", "BLOOM", "BLOWN",
    "BOARD", "BOOST", "BOUND", "BRAIN", "BRAND", "BRAVE", "BREAD", "BREAK",
    "BREED", "BRICK", "BRIEF", "BRING", "BROAD", "BROKE", "BRUSH", "BUILD",
    "BUILT", "BURST", "BUYER", "CABIN", "CABLE", "CARGO", "CARRY", "CATCH",
    "CAUSE", "CHAIN", "CHAIR", "CHAOS", "CHARM", "CHART", "CHASE", "CHEAP",
    "CHECK", "CHESS", "CHEST", "CHIEF", "CHILD", "CHINA", "CHOSE", "CIVIL",
    "CLAIM", "CLASS", "CLEAN", "CLEAR", "CLIMB", "CLING", "CLOCK", "CLONE",
    "CLOSE", "CLOUD", "COACH", "COAST", "COULD", "COUNT", "COURT", "COVER",
    "CRACK", "CRAFT", "CRASH", "CRAZY", "CREAM", "CRIME", "CROSS", "CROWD",
    "CRUEL", "CRUSH", "CURVE", "CYCLE", "DAILY", "DANCE", "DEALT", "DEATH",
    "DEBUT", "DELAY", "DENSE", "DEPTH", "DEVIL", "DIRTY", "DOUBT", "DRAFT",
    "DRAIN", "DRAMA", "DRAWN", "DREAM", "DRESS", "DRIED", "DRIFT", "DRILL",
    "DRINK", "DRIVE", "EAGER", "EARLY", "EARTH", "EIGHT", "ELDER", "ELECT",
    "ELITE", "EMAIL", "EMBED", "EMBER", "EMPTY", "ENDED", "ENEMY", "ENJOY",
    "ENTER", "ENTRY", "EQUAL", "ERROR", "ESSAY", "EVENT", "EVERY", "EXACT",
    "EXIST", "EXTRA", "FACED", "FAITH", "FALSE", "FANCY", "FATAL", "FAULT",
    "FAVOR", "FEAST", "FENCE", "FEWER", "FIBER", "FIELD", "FIFTH", "FIFTY",
    "FIGHT", "FINAL", "FIRST", "FIXED", "FLAME", "FLASH", "FLEET", "FLESH",
    "FLOAT", "FLOOD", "FLOOR", "FLOUR", "FLUID", "FOCUS", "FORCE", "FORGE",
    "FORTH", "FORUM", "FOUND", "FRAME", "FRAUD", "FRESH", "FRONT", "FROST",
    "FRUIT", "FULLY", "GIANT", "GIVEN", "GLASS", "GLOBE", "GOING", "GRACE",
    "GRADE", "GRAIN", "GRAND", "GRANT", "GRAPH", "GRASP", "GRASS", "GRAVE",
    "GREAT", "GREEN", "GREET", "GRIEF", "GRILL", "GRIND", "GROSS", "GROUP",
    "GROWN", "GUARD", "GUESS", "GUEST", "GUIDE", "GUILT", "HABIT", "HAPPY",
    "HARSH", "HEART", "HEAVY", "HENCE", "HORSE", "HOTEL", "HOUSE", "HUMAN",
    "HUMOR", "IDEAL", "IMAGE", "IMPLY", "INDEX", "INDIE", "INNER", "INPUT",
    "ISSUE", "IVORY", "JAPAN", "JOINT", "JUDGE", "JUICE", "KNOWN", "LABEL",
    "LABOR", "LARGE", "LASER", "LATER", "LAUGH", "LAYER", "LEARN", "LEASE",
    "LEAST", "LEAVE", "LEGAL", "LEVEL", "LIGHT", "LIMIT", "LINEN", "LIVER",
    "LOCAL", "LOGIC", "LOOSE", "LOVER", "LOWER", "LOYAL", "LUCKY", "LUNCH",
    "MAGIC", "MAJOR", "MAKER", "MARCH", "MATCH", "MAYOR", "MEDAL", "MEDIA",
    "MERCY", "MERGE", "MERIT", "METAL", "METER", "MIDST", "MIGHT", "MINOR",
    "MINUS", "MODEL", "MONEY", "MONTH", "MORAL", "MOUNT", "MOUSE", "MOUTH",
    "MOVED", "MOVIE", "MUSIC", "NAIVE", "NAVAL", "NERVE", "NEVER", "NEWLY",
    "NIGHT", "NOBLE", "NOISE", "NORTH", "NOTED", "NOVEL", "NURSE", "OCCUR",
    "OCEAN", "OFFER", "OFTEN", "OLIVE", "ONSET", "OPERA", "ORBIT", "ORDER",
    "OTHER", "OUTER", "OWNER", "OXIDE", "PACED", "PAINT", "PANEL", "PANIC",
    "PAPER", "PASTA", "PATCH", "PAUSE", "PEACE", "PEARL", "PHASE", "PHONE",
    "PHOTO", "PIANO", "PIECE", "PILOT", "PITCH", "PIXEL", "PLACE", "PLAIN",
    "PLANE", "PLANT", "PLATE", "PLAZA", "PLEAD", "POINT", "POUND", "POWER",
    "PRESS", "PRICE", "PRIDE", "PRIME", "PRINT", "PRIOR", "PRIZE", "PROBE",
    "PROOF", "PROUD", "PROVE", "PULSE", "PUNCH", "QUEEN", "QUEST", "QUEUE",
    "QUICK", "QUIET", "QUITE", "QUOTA", "QUOTE", "RADAR", "RADIO", "RAISE",
    "RALLY", "RANGE", "RAPID", "RATIO", "REACH", "REACT", "REALM", "REBEL",
    "REFER", "REIGN", "RELAX", "REPLY", "RIDER", "RIDGE", "RIFLE", "RIGHT",
    "RIGID", "RIVAL", "RIVER", "ROBOT", "ROOTS", "ROUGH", "ROUND", "ROUTE",
    "ROYAL", "RULED", "RULER", "RURAL", "SAINT", "SALAD", "SCALE", "SCENE",
    "SCOPE", "SCORE", "SENSE", "SERVE", "SETUP", "SEVEN", "SHALL", "SHAME",
    "SHAPE", "SHARE", "SHARK", "SHARP", "SHEER", "SHEET", "SHELF", "SHELL",
    "SHIFT", "SHINE", "SHIRT", "SHOCK", "SHOOT", "SHORT", "SHOUT", "SIGHT",
    "SINCE", "SIXTH", "SIXTY", "SIZED", "SKILL", "SKULL", "SLAVE", "SLEEP",
    "SLICE", "SLIDE", "SLOPE", "SMALL", "SMART", "SMELL", "SMILE", "SMOKE",
    "SOLID", "SOLVE", "SORRY", "SOUTH", "SPACE", "SPARE", "SPEAK", "SPEED",
    "SPEND", "SPENT", "SPIKE", "SPINE", "SPLIT", "SPOKE", "SPORT", "SPRAY",
    "SQUAD", "STAFF", "STAGE", "STAKE", "STALE", "STALL", "STAMP", "STAND",
    "STARK", "START", "STATE", "STEAL", "STEAM", "STEEL", "STEEP", "STEER",
    "STERN", "STICK", "STILL", "STOCK", "STONE", "STOOD", "STORE", "STORM",
    "STORY", "STOVE", "STRIP", "STUCK", "STUDY", "STUFF", "STYLE", "SUGAR",
    "SUITE", "SUPER", "SURGE", "SWEAR", "SWEEP", "SWEET", "SWEPT", "SWIFT",
    "SWING", "SWORD", "SWORE", "SWORN", "TABLE", "TASTE", "TEACH", "TEMPO",
    "THEME", "THERE", "THICK", "THING", "THINK", "THIRD", "THOSE", "THREE",
    "THREW", "THROW", "THUMB", "TIGHT", "TIMER", "TITLE", "TODAY", "TOKEN",
    "TOTAL", "TOUCH", "TOUGH", "TOWER", "TOXIC", "TRACE", "TRACK", "TRADE",
    "TRAIL", "TRAIN", "TRAIT", "TRASH", "TREAT", "TREND", "TRIAL", "TRIBE",
    "TRICK", "TRIED", "TROOP", "TRUCK", "TRULY", "TRUMP", "TRUNK", "TRUST",
    "TRUTH", "TUMOR", "TWICE", "TWIST", "ULTRA", "UNCLE", "UNDER", "UNION",
    "UNITE", "UNITY", "UNTIL", "UPPER", "UPSET", "URBAN", "USAGE", "USUAL",
    "UTTER", "VALID", "VALUE", "VIDEO", "VIGOR", "VIRUS", "VISIT", "VITAL",
    "VIVID", "VOCAL", "VOICE", "VOTER", "WASTE", "WATCH", "WATER", "WEIGH",
    "WEIRD", "WHERE", "WHICH", "WHILE", "WHITE", "WHOLE", "WHOSE", "WOMAN",
    "WORLD", "WORSE", "WORST", "WORTH", "WOULD", "WOUND", "WRITE", "WRONG",
    "WROTE", "YIELD", "YOUNG", "YOUTH",
]

WORDS_4 = [
    "ABLE", "ACID", "AGED", "AIDE", "ALLY", "AMID", "ARCH", "AREA", "ARMY",
    "ARTS", "ASKS", "ATOM", "AUTO", "BACK", "BAIL", "BAIT", "BAND", "BANK",
    "BARE", "BARN", "BASE", "BATH", "BEAM", "BEAN", "BEAR", "BEAT", "BEEN",
    "BEER", "BELL", "BELT", "BEND", "BEST", "BIKE", "BILL", "BIND", "BIRD",
    "BITE", "BLOW", "BLUE", "BLUR", "BOAT", "BOLD", "BOLT", "BOMB", "BOND",
    "BONE", "BOOK", "BOOM", "BOOT", "BORE", "BORN", "BOSS", "BOTH", "BOWL",
    "BULK", "BULL", "BURN", "BUSY", "CAFE", "CAGE", "CAKE", "CALL", "CALM",
    "CAME", "CAMP", "CAPE", "CARD", "CARE", "CART", "CASE", "CASH", "CAST",
    "CELL", "CHIP", "CITE", "CITY", "CLAN", "CLIP", "CLUB", "CLUE", "COAL",
    "COAT", "CODE", "COIN", "COLD", "COME", "COOK", "COOL", "COPE", "COPY",
    "CORD", "CORE", "CORN", "COST", "CREW", "CROP", "CURE", "CUTE", "DALE",
    "DAME", "DARE", "DARK", "DART", "DATA", "DATE", "DAWN", "DAYS", "DEAD",
    "DEAF", "DEAL", "DEAR", "DEBT", "DECK", "DEED", "DEEM", "DEEP", "DEER",
    "DEMO", "DENY", "DESK", "DIAL", "DICE", "DIET", "DIRT", "DISC", "DISH",
    "DISK", "DOCK", "DOES", "DOME", "DONE", "DOOM", "DOOR", "DOSE", "DOWN",
    "DRAG", "DRAW", "DROP", "DRUM", "DUAL", "DUDE", "DULL", "DUMB", "DUMP",
    "DUST", "DUTY", "EACH", "EARN", "EASE", "EAST", "EASY", "EDGE", "EDIT",
    "ELSE", "EMIT", "EPIC", "EURO", "EVEN", "EVER", "EVIL", "EXAM", "EXEC",
    "EXIT", "FACE", "FACT", "FADE", "FAIL", "FAIR", "FAKE", "FALL", "FAME",
    "FARM", "FAST", "FATE", "FEAR", "FEAT", "FEED", "FEEL", "FEES", "FELL",
    "FELT", "FILE", "FILL", "FILM", "FIND", "FINE", "FIRE", "FIRM", "FISH",
    "FIST", "FLAG", "FLAT", "FLED", "FLEW", "FLIP", "FLOW", "FOAM", "FOLD",
    "FOLK", "FOND", "FONT", "FOOD", "FOOL", "FOOT", "FORD", "FORE", "FORK",
    "FORM", "FORT", "FOUL", "FOUR", "FREE", "FROM", "FUEL", "FULL", "FUND",
    "FURY", "FUSE", "GAIN", "GAIT", "GALE", "GAME", "GANG", "GATE", "GAVE",
    "GAZE", "GEAR", "GENE", "GIFT", "GIRL", "GIVE", "GLAD", "GLOW", "GLUE",
    "GOAL", "GOES", "GOLD", "GOLF", "GONE", "GOOD", "GRAB", "GRAY", "GREW",
    "GRID", "GRIM", "GRIP", "GROW", "GULF", "GURU", "HACK", "HAIR", "HALF",
    "HALL", "HALT", "HAND", "HANG", "HARD", "HARM", "HASH", "HATE", "HAUL",
    "HAVE", "HEAD", "HEAL", "HEAP", "HEAR", "HEAT", "HEEL", "HELD", "HELP",
    "HERB", "HERE", "HERO", "HIGH", "HIKE", "HILL", "HINT", "HIRE", "HOLD",
    "HOLE", "HOME", "HOOD", "HOOK", "HOPE", "HOST", "HOUR", "HUGE", "HUNG",
    "HUNT", "HURT", "ICON", "IDEA", "INCH", "INTO", "IRON", "ISLE", "ITEM",
    "JACK", "JAIL", "JAZZ", "JOBS", "JOIN", "JOKE", "JUMP", "JURY", "JUST",
    "KEEN", "KEEP", "KEPT", "KICK", "KILL", "KIND", "KING", "KNEE", "KNEW",
    "KNOT", "KNOW", "LACK", "LAID", "LAKE", "LAMP", "LAND", "LANE", "LAPS",
    "LAST", "LATE", "LAWN", "LEAD", "LEAN", "LEAP", "LEFT", "LEND", "LENS",
    "LESS", "LIED", "LIFE", "LIFT", "LIKE", "LIME", "LINE", "LINK", "LION",
    "LIST", "LIVE", "LOAD", "LOAN", "LOCK", "LOGO", "LONG", "LOOK", "LORD",
    "LOSE", "LOSS", "LOST", "LOTS", "LOUD", "LOVE", "LUCK", "LURE", "LUSH",
    "MADE", "MAIL", "MAIN", "MAKE", "MALE", "MALL", "MANY", "MAPS", "MARK",
    "MARS", "MASK", "MASS", "MATE", "MAZE", "MEAL", "MEAN", "MEAT", "MEET",
    "MELT", "MEMO", "MENU", "MERE", "MESH", "MESS", "MICE", "MILD", "MILE",
    "MILK", "MILL", "MIND", "MINE", "MINT", "MISS", "MODE", "MOLE", "MOOD",
    "MOON", "MORE", "MOSS", "MOST", "MOVE", "MUCH", "MUST", "MYTH", "NAIL",
    "NAME", "NAVY", "NEAR", "NEAT", "NECK", "NEED", "NEWS", "NEXT", "NICE",
    "NINE", "NODE", "NONE", "NORM", "NOSE", "NOTE", "NOUN", "OATH", "OBEY",
    "ODDS", "OILS", "OKAY", "ONCE", "ONLY", "ONTO", "OPEN", "ORAL", "ORCA",
    "OVEN", "OVER", "PACE", "PACK", "PAGE", "PAID", "PAIN", "PAIR", "PALE",
    "PALM", "PANT", "PARK", "PART", "PASS", "PAST", "PATH", "PEAK", "PEER",
    "PETS", "PICK", "PIER", "PILE", "PINE", "PIPE", "PLAN", "PLAY", "PLEA",
    "PLOT", "PLUG", "PLUS", "POEM", "POET", "POLE", "POLL", "POLO", "POND",
    "POOL", "POOR", "POPE", "PORK", "PORT", "POSE", "POST", "POUR", "PRAY",
    "PREY", "PROP", "PULL", "PUMP", "PURE", "PUSH", "QUIT", "QUIZ", "RACE",
    "RACK", "RAGE", "RAID", "RAIL", "RAIN", "RANK", "RARE", "RATE", "READ",
    "REAL", "REAR", "RELY", "RENT", "REST", "RICE", "RICH", "RIDE", "RING",
    "RIOT", "RISE", "RISK", "ROAD", "ROCK", "RODE", "ROLE", "ROLL", "ROOF",
    "ROOM", "ROOT", "ROPE", "ROSE", "RUIN", "RULE", "RUSH", "SAFE", "SAGE",
    "SAID", "SAIL", "SAKE", "SALE", "SALT", "SAME", "SAND", "SANG", "SAVE",
    "SEAL", "SEAT", "SEED", "SEEK", "SEEM", "SEEN", "SELF", "SELL", "SEND",
    "SENT", "SHED", "SHIP", "SHOP", "SHOT", "SHOW", "SHUT", "SICK", "SIDE",
    "SIGH", "SIGN", "SILK", "SINK", "SITE", "SIZE", "SKIN", "SKIP", "SLAM",
    "SLAP", "SLIM", "SLIP", "SLOT", "SLOW", "SNAP", "SNOW", "SOAP", "SOAR",
    "SOCK", "SOFT", "SOIL", "SOLD", "SOLE", "SOME", "SONG", "SOON", "SORT",
    "SOUL", "SOUR", "SPAN", "SPIN", "SPOT", "STAR", "STAY", "STEM", "STEP",
    "STIR", "STOP", "STUB", "SUCH", "SUIT", "SUNG", "SURE", "SURF", "SWAP",
    "SWIM", "TAIL", "TAKE", "TALE", "TALK", "TALL", "TANK", "TAPE", "TASK",
    "TAXI", "TEAL", "TEAM", "TEAR", "TECH", "TELL", "TEND", "TENS", "TENT",
    "TERM", "TEST", "TEXT", "THAN", "THAT", "THEM", "THEN", "THEY", "THIN",
    "THIS", "THUS", "TICK", "TIDE", "TIDY", "TIED", "TIER", "TILE", "TILL",
    "TIME", "TINY", "TIRE", "TOLD", "TOLL", "TOMB", "TONE", "TOOK", "TOOL",
    "TOPS", "TORE", "TORN", "TOUR", "TOWN", "TRAP", "TRAY", "TREE", "TRIM",
    "TRIO", "TRIP", "TRUE", "TUBE", "TUCK", "TUNE", "TURN", "TYPE", "UGLY",
    "UNIT", "UPON", "URGE", "USED", "USER", "VAIN", "VALE", "VARY", "VAST",
    "VERB", "VERY", "VEST", "VICE", "VIEW", "VINE", "VOID", "VOLT", "VOTE",
    "WADE", "WAGE", "WAIT", "WAKE", "WALK", "WALL", "WANT", "WARD", "WARM",
    "WARN", "WASH", "WAVE", "WEAK", "WEAR", "WEED", "WEEK", "WEIR", "WELL",
    "WENT", "WERE", "WEST", "WHAT", "WHEN", "WHOM", "WIDE", "WIFE", "WILD",
    "WILL", "WIND", "WINE", "WING", "WIRE", "WISE", "WISH", "WITH", "WOKE",
    "WOMB", "WOOD", "WOOL", "WORD", "WORE", "WORK", "WORM", "WORN", "WRAP",
    "YARD", "YEAR", "YOUR", "ZERO", "ZONE", "ZOOM",
]

WORDS_3 = [
    "ACE", "ACT", "ADD", "AGE", "AGO", "AID", "AIM", "AIR", "ALE", "ALL",
    "AND", "ANT", "ANY", "APE", "ARC", "ARE", "ARK", "ARM", "ART", "ASH",
    "ATE", "AWE", "AXE", "BAD", "BAG", "BAN", "BAR", "BAT", "BAY", "BED",
    "BET", "BIG", "BIT", "BOW", "BOX", "BOY", "BUD", "BUG", "BUS", "BUT",
    "BUY", "CAB", "CAN", "CAP", "CAR", "COP", "COW", "CRY", "CUB", "CUP",
    "CUT", "DAD", "DAM", "DAY", "DEN", "DEW", "DID", "DIG", "DIM", "DIP",
    "DOC", "DOG", "DOT", "DRY", "DUB", "DUE", "DUG", "DUO", "DYE", "EAR",
    "EAT", "EEL", "EGG", "EGO", "ELF", "ELM", "EMU", "END", "ERA", "EVE",
    "EWE", "EYE", "FAN", "FAR", "FAT", "FAX", "FED", "FEE", "FEW", "FIG",
    "FIN", "FIT", "FIX", "FLU", "FLY", "FOE", "FOG", "FOR", "FOX", "FRY",
    "FUN", "FUR", "GAP", "GAS", "GAY", "GEL", "GEM", "GET", "GOD", "GOT",
    "GUM", "GUN", "GUT", "GUY", "GYM", "HAD", "HAM", "HAS", "HAT", "HAY",
    "HEN", "HER", "HEW", "HID", "HIM", "HIP", "HIS", "HIT", "HOG", "HOP",
    "HOT", "HOW", "HUB", "HUE", "HUG", "HUT", "ICE", "ICY", "ILL", "INK",
    "INN", "ION", "IRE", "ITS", "IVY", "JAB", "JAM", "JAR", "JAW", "JAY",
    "JET", "JOB", "JOG", "JOT", "JOY", "JUG", "KEY", "KID", "KIN", "KIT",
    "LAB", "LAD", "LAP", "LAW", "LAY", "LED", "LEG", "LET", "LID", "LIE",
    "LIP", "LIT", "LOG", "LOT", "LOW", "MAD", "MAP", "MAT", "MAY", "MEN",
    "MET", "MIX", "MOB", "MOM", "MOP", "MUD", "MUG", "NAP", "NET", "NEW",
    "NIT", "NOD", "NOR", "NOT", "NOW", "NUN", "NUT", "OAK", "OAR", "OAT",
    "ODD", "ODE", "OFF", "OIL", "OLD", "ONE", "OPT", "ORB", "ORE", "OUR",
    "OUT", "OWE", "OWL", "OWN", "PAD", "PAN", "PAT", "PAW", "PAY", "PEA",
    "PEG", "PEN", "PER", "PET", "PIE", "PIG", "PIN", "PIT", "PLY", "POD",
    "POP", "POT", "PRY", "PUB", "PUN", "PUP", "PUT", "RAG", "RAM", "RAN",
    "RAP", "RAT", "RAW", "RAY", "RED", "REF", "RIB", "RID", "RIG", "RIM",
    "RIP", "ROB", "ROD", "ROT", "ROW", "RUB", "RUG", "RUN", "RUT", "RYE",
    "SAD", "SAP", "SAT", "SAW", "SAY", "SEA", "SET", "SEW", "SHE", "SHY",
    "SIN", "SIP", "SIS", "SIT", "SIX", "SKI", "SKY", "SLY", "SOB", "SOD",
    "SON", "SOP", "SOT", "SOW", "SOY", "SPA", "SPY", "STY", "SUB", "SUM",
    "SUN", "TAB", "TAG", "TAN", "TAP", "TAR", "TAX", "TEA", "TEN", "THE",
    "TIE", "TIN", "TIP", "TOE", "TON", "TOO", "TOP", "TOW", "TOY", "TUB",
    "TUG", "TWO", "URN", "USE", "VAN", "VAT", "VET", "VIA", "VIE", "VOW",
    "WAR", "WAX", "WAY", "WEB", "WED", "WET", "WHO", "WHY", "WIG", "WIN",
    "WIT", "WOE", "WOK", "WON", "WOO", "WOW", "YAM", "YAP", "YEA", "YES",
    "YET", "YEW", "YOU", "ZAP", "ZEN", "ZIP", "ZOO",
]

# Build word sets by length
WORD_SETS = {
    3: set(WORDS_3),
    4: set(WORDS_4),
    5: set(WORDS_5),
}

# Build prefix indexes
WORD_BY_PREFIX = {}
for length, words in [(3, WORDS_3), (4, WORDS_4), (5, WORDS_5)]:
    for w in words:
        for i in range(1, length + 1):
            prefix = w[:i]
            key = (length, prefix)
            WORD_BY_PREFIX.setdefault(key, set()).add(w)


def get_words_with_prefix(length, prefix):
    """Get all words of given length starting with prefix."""
    return WORD_BY_PREFIX.get((length, prefix), set())


# Grid layout: 5x5 with black squares at (0,4) and (4,0) — rotationally symmetric
# . . . . #
# . . . . .
# . . . . .
# . . . . .
# # . . . .
#
# Across slots:
#   1A: row 0, cols 0-3 (4 letters)
#   5A: row 1, cols 0-4 (5 letters)
#   6A: row 2, cols 0-4 (5 letters)
#   7A: row 3, cols 0-4 (5 letters)
#   8A: row 4, cols 1-4 (4 letters)
#
# Down slots:
#   1D: col 0, rows 0-3 (4 letters)
#   2D: col 1, rows 0-4 (5 letters)
#   3D: col 2, rows 0-4 (5 letters)
#   4D: col 3, rows 0-4 (5 letters)
#   5D: col 4, rows 1-4 (4 letters)

ACROSS_SLOTS = [
    ("1A", 0, 0, 4, "across"),  # row, col_start, length, direction
    ("5A", 1, 0, 5, "across"),
    ("6A", 2, 0, 5, "across"),
    ("7A", 3, 0, 5, "across"),
    ("8A", 4, 1, 4, "across"),
]

DOWN_SLOTS = [
    ("1D", 0, 0, 4, "down"),  # row_start, col, length, direction
    ("2D", 0, 1, 5, "down"),
    ("3D", 0, 2, 5, "down"),
    ("4D", 0, 3, 5, "down"),
    ("5D", 1, 4, 4, "down"),
]


def solve_grid(max_attempts=5000):
    """Fill the grid using backtracking on word slots."""
    # We'll fill across slots first, checking down constraints as we go.
    # Grid is 5x5, initialize with None (unfilled) and '#' for black squares.
    grid = [[None]*5 for _ in range(5)]
    grid[0][4] = '#'
    grid[4][0] = '#'

    # Order of filling: 1A, then rows 1-3 (5-letter), then 8A
    # After each across word, verify all down columns remain viable.

    across_order = ACROSS_SLOTS  # Fill in order

    for attempt in range(max_attempts):
        # Reset grid
        for r in range(5):
            for c in range(5):
                if grid[r][c] != '#':
                    grid[r][c] = None

        if _fill_across(grid, 0, across_order):
            # Verify all down words are valid
            all_valid = True
            down_words = []
            for name, r_start, col, length, _ in DOWN_SLOTS:
                word = ''.join(grid[r_start + i][col] for i in range(length))
                if word not in WORD_SETS[length]:
                    all_valid = False
                    break
                down_words.append(word)

            if all_valid:
                across_words = []
                for name, row, c_start, length, _ in ACROSS_SLOTS:
                    word = ''.join(grid[row][c_start + i] for i in range(length))
                    across_words.append(word)

                # Check no duplicate answers
                all_words = across_words + down_words
                if len(set(all_words)) == len(all_words):
                    print(f"Found valid grid after {attempt + 1} attempts:")
                    for r in range(5):
                        print(' '.join(grid[r][c] if grid[r][c] != '#' else '.' for c in range(5)))
                    print(f"Across: {across_words}")
                    print(f"Down:   {down_words}")
                    return grid

    print("No grid found within attempt limit.")
    return None


def _fill_across(grid, slot_idx, across_order):
    """Recursively fill across slots."""
    if slot_idx >= len(across_order):
        return True

    name, row, c_start, length, _ = across_order[slot_idx]

    # Get candidate words
    candidates = list(WORD_SETS[length])
    random.shuffle(candidates)

    for word in candidates[:200]:  # Limit candidates per slot
        # Place word
        for i, ch in enumerate(word):
            grid[row][c_start + i] = ch

        # Check all down columns remain viable
        viable = True
        for _, r_start, col, d_len, _ in DOWN_SLOTS:
            prefix = ''
            for i in range(d_len):
                cell = grid[r_start + i][col]
                if cell is None:
                    break
                prefix += cell

            if prefix and not get_words_with_prefix(d_len, prefix):
                viable = False
                break

        if viable and _fill_across(grid, slot_idx + 1, across_order):
            return True

        # Undo
        for i in range(length):
            grid[row][c_start + i] = None

    return False


def grid_to_json(grid, date="2026-03-27"):
    """Convert a solved grid to the puzzle JSON format."""
    size = 5

    # Build the grid array
    grid_arr = []
    for r in range(size):
        row = []
        for c in range(size):
            row.append(grid[r][c] if grid[r][c] != '#' else '#')
        grid_arr.append(row)

    # Number the cells
    clue_number = 1
    cell_numbers = {}
    for r in range(size):
        for c in range(size):
            if grid[r][c] == '#':
                continue
            starts_across = (c == 0 or grid[r][c-1] == '#') and c + 1 < size and grid[r][c+1] != '#'
            starts_down = (r == 0 or grid[r-1][c] == '#') and r + 1 < size and grid[r+1][c] != '#'
            # Also check for 3+ letter runs
            if starts_across:
                run = 0
                for i in range(c, size):
                    if grid[r][i] == '#':
                        break
                    run += 1
                if run < 3:
                    starts_across = False
            if starts_down:
                run = 0
                for i in range(r, size):
                    if grid[i][c] == '#':
                        break
                    run += 1
                if run < 3:
                    starts_down = False

            if starts_across or starts_down:
                cell_numbers[(r, c)] = clue_number
                clue_number += 1

    # Build clues
    across_clues = []
    down_clues = []

    for r in range(size):
        c = 0
        while c < size:
            if grid[r][c] == '#':
                c += 1
                continue
            # Check if this starts an across word
            if c == 0 or grid[r][c-1] == '#':
                word = ''
                start_c = c
                while c < size and grid[r][c] != '#':
                    word += grid[r][c]
                    c += 1
                if len(word) >= 3 and (r, start_c) in cell_numbers:
                    across_clues.append({
                        "number": cell_numbers[(r, start_c)],
                        "clue": f"[Clue for {word}]",
                        "answer": word,
                        "row": r,
                        "col": start_c,
                        "length": len(word),
                    })
            else:
                c += 1

    for c in range(size):
        r = 0
        while r < size:
            if grid[r][c] == '#':
                r += 1
                continue
            if r == 0 or grid[r-1][c] == '#':
                word = ''
                start_r = r
                while r < size and grid[r][c] != '#':
                    word += grid[r][c]
                    r += 1
                if len(word) >= 3 and (start_r, c) in cell_numbers:
                    down_clues.append({
                        "number": cell_numbers[(start_r, c)],
                        "clue": f"[Clue for {word}]",
                        "answer": word,
                        "row": start_r,
                        "col": c,
                        "length": len(word),
                    })
            else:
                r += 1

    return {
        "date": date,
        "size": size,
        "grid": grid_arr,
        "clues": {
            "across": across_clues,
            "down": down_clues,
        }
    }


if __name__ == "__main__":
    random.seed(int(sys.argv[1]) if len(sys.argv) > 1 else 42)
    grid = solve_grid()
    if grid:
        puzzle = grid_to_json(grid)
        # Write to file
        out_path = Path(__file__).parent.parent / "puzzles" / "2026-03-27.json"
        # Add placeholder clues
        clues = puzzle["clues"]
        sample_across_clues = [
            "Trade policy tool dominating White House headlines",
            "What the Federal Reserve did to interest rates this month",
            "NATO alliance response to the latest security threat",
            "Congressional hearing topic that trended on social media",
            "Result of the weekend's biggest upset in March Madness",
        ]
        sample_down_clues = [
            "Tech giant facing a major antitrust ruling",
            "Viral social media challenge sweeping TikTok this week",
            "Climate summit location announced by the UN",
            "Cabinet nominee awaiting Senate confirmation",
            "Box office hit that broke opening weekend records",
        ]
        for i, c in enumerate(clues["across"]):
            c["clue"] = sample_across_clues[i] if i < len(sample_across_clues) else f"Clue for {c['answer']}"
        for i, c in enumerate(clues["down"]):
            c["clue"] = sample_down_clues[i] if i < len(sample_down_clues) else f"Clue for {c['answer']}"

        with open(out_path, 'w') as f:
            json.dump(puzzle, f, indent=2)
        print(f"\nPuzzle written to {out_path}")
        print(json.dumps(puzzle, indent=2))
