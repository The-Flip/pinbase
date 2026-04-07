"""Seed data for book citation sources."""

BOOK_SOURCES: list[dict] = [
    # =====================================================================
    # Multi-edition works (root + children)
    # =====================================================================
    {
        "name": "The Encyclopedia of Pinball",
        "source_type": "book",
        "author": "Richard M. Bueschel",
        "publisher": "Silverball Amusements",
        "description": (
            "Planned six-volume history of early pinball. Two volumes "
            "published before Bueschel's death in 1998."
        ),
        "children": [
            {
                "name": "The Encyclopedia of Pinball, Vol. 1: Whiffle to Rocket 1930–1933",
                "source_type": "book",
                "author": "Richard M. Bueschel",
                "publisher": "Silverball Amusements",
                "year": 1996,
                "isbn": "9781889933009",
                "description": (
                    "Planned six-volume history of early pinball. Vol. 1 "
                    "covers the birth of pinball from bagatelle-derived "
                    "games through the first flipperless models."
                ),
            },
            {
                "name": "The Encyclopedia of Pinball, Vol. 2: Contact to Bumper 1934–1936",
                "source_type": "book",
                "author": "Richard M. Bueschel",
                "publisher": "Silverball Amusements",
                "year": 1997,
                "isbn": "9781889933023",
                "description": (
                    "Planned six-volume history of early pinball. Vol. 2 "
                    "covers the expansion of pinball with contact holes, "
                    "bumpers, and battery-powered features."
                ),
            },
        ],
    },
    {
        "name": "Pinball!",
        "source_type": "book",
        "author": "Roger C. Sharpe",
        "publisher": "E.P. Dutton",
        "description": (
            "Photographic survey of pinball history and culture. Sharpe is "
            "known for the 1976 demonstration that saved pinball in New York City."
        ),
        "children": [
            {
                "name": "Pinball!, hardcover",
                "source_type": "book",
                "author": "Roger C. Sharpe",
                "publisher": "E.P. Dutton",
                "year": 1977,
                "isbn": "9780525179757",
                "description": (
                    "Photographic survey of pinball history and culture. "
                    "Sharpe is known for the 1976 demonstration that saved "
                    "pinball in New York City."
                ),
            },
            {
                "name": "Pinball!, paperback",
                "source_type": "book",
                "author": "Roger C. Sharpe",
                "publisher": "E.P. Dutton",
                "year": 1977,
                "isbn": "9780525474814",
                "description": (
                    "Photographic survey of pinball history and culture. "
                    "Sharpe is known for the 1976 demonstration that saved "
                    "pinball in New York City."
                ),
            },
        ],
    },
    {
        "name": "Pinball Machines",
        "source_type": "book",
        "author": "Heribert Eiden, Jürgen Lukas",
        "publisher": "Schiffer Publishing",
        "description": (
            "Visual guide to pinball machines, translated from the German "
            "Flipper Scheiben."
        ),
        "children": [
            {
                "name": "Pinball Machines, 1st edition",
                "source_type": "book",
                "author": "Heribert Eiden, Jürgen Lukas",
                "publisher": "Schiffer Publishing",
                "year": 1992,
                "isbn": "9780887404313",
                "description": (
                    "Visual guide to pinball machines, translated from the "
                    "German Flipper Scheiben."
                ),
            },
            {
                "name": "Pinball Machines, revised edition",
                "source_type": "book",
                "author": "Heribert Eiden, Jürgen Lukas",
                "publisher": "Schiffer Publishing",
                "year": 1997,
                "isbn": "9780764303166",
                "description": (
                    "Visual guide to pinball machines, translated from the "
                    "German Flipper Scheiben."
                ),
            },
            {
                "name": "Pinball Machines, 3rd revised edition",
                "source_type": "book",
                "author": "Heribert Eiden, Jürgen Lukas",
                "publisher": "Schiffer Publishing",
                "year": 1999,
                "isbn": "9780764308956",
                "description": (
                    "Visual guide to pinball machines, translated from the "
                    "German Flipper Scheiben."
                ),
            },
        ],
    },
    {
        "name": "The Complete Pinball Book",
        "source_type": "book",
        "author": "Marco Rossignoli",
        "publisher": "Schiffer Publishing",
        "description": (
            "Comprehensive history of pinball covering game design, "
            "artwork, and collecting."
        ),
        "children": [
            {
                "name": "The Complete Pinball Book, 1st edition",
                "source_type": "book",
                "author": "Marco Rossignoli",
                "publisher": "Schiffer Publishing",
                "year": 1999,
                "isbn": "9780764310034",
                "description": (
                    "Comprehensive history of pinball covering game design, "
                    "artwork, and collecting."
                ),
            },
            {
                "name": "The Complete Pinball Book, 2nd revised edition",
                "source_type": "book",
                "author": "Marco Rossignoli",
                "publisher": "Schiffer Publishing",
                "year": 2002,
                "isbn": "9780764315862",
                "description": (
                    "Comprehensive history of pinball covering game design, "
                    "artwork, and collecting."
                ),
            },
            {
                "name": "The Complete Pinball Book, 3rd revised edition",
                "source_type": "book",
                "author": "Marco Rossignoli",
                "publisher": "Schiffer Publishing",
                "year": 2011,
                "isbn": "9780764337857",
                "description": (
                    "Comprehensive history of pinball covering game design, "
                    "artwork, and collecting."
                ),
            },
        ],
    },
    {
        "name": "The Pinball Compendium: 1982 to the Present",
        "source_type": "book",
        "author": "Michael Shalhoub",
        "publisher": "Schiffer Publishing",
        "description": (
            "Color photo reference of solid-state and DMD-era pinball "
            "machines from 1982 onward. Part of Shalhoub's four-volume "
            "Pinball Compendium series."
        ),
        "children": [
            {
                "name": "The Pinball Compendium: 1982 to the Present, 1st edition",
                "source_type": "book",
                "author": "Michael Shalhoub",
                "publisher": "Schiffer Publishing",
                "year": 2005,
                "isbn": "9780764323003",
                "description": (
                    "Color photo reference of solid-state and DMD-era pinball "
                    "machines from 1982 onward. Part of Shalhoub's four-volume "
                    "Pinball Compendium series."
                ),
            },
            {
                "name": "The Pinball Compendium: 1982 to the Present, 2nd revised and expanded edition",
                "source_type": "book",
                "author": "Michael Shalhoub",
                "publisher": "Schiffer Publishing",
                "year": 2012,
                "isbn": "9780764341076",
                "description": (
                    "Color photo reference of solid-state and DMD-era pinball "
                    "machines from 1982 onward. Part of Shalhoub's four-volume "
                    "Pinball Compendium series."
                ),
            },
        ],
    },
    # =====================================================================
    # Single-edition (flat, no children)
    # =====================================================================
    {
        "name": "Pinball One: Bagatelle to Baffle Ball 1775–1931",
        "source_type": "book",
        "author": "Richard M. Bueschel",
        "publisher": "Hoflin Publishing",
        "year": 1988,
        "isbn": "9780866670470",
        "description": (
            "Bueschel's earlier history of pre-flipper pinball, predecessor "
            "to The Encyclopedia of Pinball."
        ),
    },
    {
        "name": "Pinball Wizardry",
        "source_type": "book",
        "author": "Robert Polin, Michael Rain",
        "publisher": "Prentice-Hall",
        "year": 1979,
        "isbn": "9780136762218",
        "description": (
            "Playing strategy and tips guide from the late 1970s golden age."
        ),
    },
    {
        "name": "Pinball Memories: Forty Years of Fun 1958–1998",
        "source_type": "book",
        "author": "Marco Rossignoli",
        "publisher": "Schiffer Publishing",
        "year": 2002,
        "isbn": "9780764316876",
        "description": (
            "800+ color photos covering 50 machines from the flipper era "
            "through the 1990s."
        ),
    },
    {
        "name": "Pinball Snapshots: Air Aces to Xenon",
        "source_type": "book",
        "author": "Marco Rossignoli, Graham McGuiness",
        "publisher": "Schiffer Publishing",
        "year": 2004,
        "isbn": "9780764321092",
        "description": ("Detailed profiles of 50 machines with 500+ color photos."),
    },
    {
        "name": "Pinball Perspectives: Ace High to World's Series",
        "source_type": "book",
        "author": "Marco Rossignoli, Graham McGuiness",
        "publisher": "Schiffer Publishing",
        "year": 2007,
        "isbn": "9780764326097",
        "description": (
            "Profiles of 50 machines with 400+ color photos. Third in "
            "Rossignoli's photo reference series."
        ),
    },
    {
        "name": "The Pinball Compendium: 1930s–1960s",
        "source_type": "book",
        "author": "Michael Shalhoub",
        "publisher": "Schiffer Publishing",
        "year": 2002,
        "isbn": "9780764315275",
        "description": (
            "Color photo reference of pre-war through early solid-state "
            "pinball. First in Shalhoub's four-volume series; overlaps "
            "with the later Electro-Mechanical Era volume."
        ),
    },
    {
        "name": "The Pinball Compendium: Electro-Mechanical Era",
        "source_type": "book",
        "author": "Michael Shalhoub",
        "publisher": "Schiffer Publishing",
        "year": 2008,
        "isbn": "9780764330285",
        "description": (
            "1,000+ color photos of electromechanical pinball machines from "
            "the 1930s–1970s. Broader and more comprehensive than the "
            "earlier 1930s–1960s volume."
        ),
    },
    {
        "name": "The Pinball Compendium: 1970–1981",
        "source_type": "book",
        "author": "Michael Shalhoub",
        "publisher": "Schiffer Publishing",
        "year": 2004,
        "isbn": "9780764320743",
        "description": (
            "Color photo reference covering the transition from "
            "electromechanical to early solid-state pinball."
        ),
    },
    {
        "name": "Your Pinball Machine",
        "source_type": "book",
        "author": "B.B. Kamoroff",
        "publisher": "Schiffer Publishing",
        "year": 2021,
        "isbn": "9780764361807",
        "description": (
            "Practical guide to purchasing, adjusting, maintaining, and "
            "repairing home pinball machines."
        ),
    },
    {
        "name": "Pinball: A Graphic History of the Silver Ball",
        "source_type": "book",
        "author": "Jon Chad",
        "publisher": "First Second",
        "year": 2022,
        "isbn": "9781250249210",
        "description": (
            "Nonfiction graphic novel covering pinball history from the "
            "1700s to the present."
        ),
    },
    {
        "name": "Pinball: A Quest for Mastery",
        "source_type": "book",
        "author": "Tasker Smith",
        "publisher": "Schiffer Publishing",
        "year": 2026,
        "isbn": "9780764365027",
        "description": "Guide to competitive pinball technique and mastery.",
    },
    {
        "name": "Tilt: The Pinball Book",
        "source_type": "book",
        "author": "Candace Ford Tolbert, Jim Alan Tolbert",
        "publisher": "Creative Arts Book Company",
        "year": 1978,
        "isbn": "9780916870140",
        "description": (
            "Home maintenance, history, and playing tips for pinball machines."
        ),
    },
    {
        "name": "Pinball Reference Guide",
        "source_type": "book",
        "author": "Donald Mueting, Robert Hawkins",
        "publisher": "Mead Co.",
        "year": 1979,
        "isbn": "9780934422192",
        "description": (
            "Pocket-sized listing of 2,500+ pinball games. Precursor to "
            "the Pinball Collector's Resource (1992)."
        ),
    },
    {
        "name": "From Pinballs to Pixels",
        "source_type": "book",
        "author": "Ken Horowitz",
        "publisher": "McFarland",
        "year": 2023,
        "isbn": "9781476689371",
        "description": (
            "History of Williams-Bally-Midway with 40+ interviews covering "
            "pinball and arcade games."
        ),
    },
]
