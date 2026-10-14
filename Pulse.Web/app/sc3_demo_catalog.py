"""ScoreConnect III catalogue for demo mode.

Captured read-only from a real SC III install (vpu-home, 2026-09-29) through
its local REST API: the full vendor list, plus the sport and connection-type
lists for the four brands the scoreboard chain draws (Daktronics, Fairplay,
Nevco, Electro-Mech) and one wireless-only vendor (FairPlay MP80 Wireless).
Vendors outside those five return an empty sport list in demo mode.

Ids are SC III's own. Connection-type ids are per vendor (Daktronics Wired is
11, Electro-Mech Wired is 17), which is the trap the editor has to respect.
"""

CATALOG = {
 "vendors": [
  {
   "id": 52,
   "description": "Alge"
  },
  {
   "id": 25,
   "description": "Alge Timing CKN"
  },
  {
   "id": 24,
   "description": "All American Model 3000"
  },
  {
   "id": 14,
   "description": "All American Model 8000"
  },
  {
   "id": 140,
   "description": "All American Model 9000"
  },
  {
   "id": 51,
   "description": "Anatec"
  },
  {
   "id": 251,
   "description": "Anatec Wireless"
  },
  {
   "id": 60,
   "description": "Atlas Servis CZ"
  },
  {
   "id": 66,
   "description": "Baybor"
  },
  {
   "id": 10,
   "description": "Bertelle"
  },
  {
   "id": 72,
   "description": "Bicen"
  },
  {
   "id": 61,
   "description": "Blue Vane"
  },
  {
   "id": 15,
   "description": "Bodet"
  },
  {
   "id": 48,
   "description": "Colorado Timing"
  },
  {
   "id": 49,
   "description": "ColoradoTiming V2"
  },
  {
   "id": 69,
   "description": "Colosseo"
  },
  {
   "id": 50,
   "description": "Compulink"
  },
  {
   "id": 29,
   "description": "Cuma"
  },
  {
   "id": 1,
   "description": "Daktronics"
  },
  {
   "id": 18,
   "description": "Daktronics 4000"
  },
  {
   "id": 47,
   "description": "Daktronics 4000 V2"
  },
  {
   "id": 6,
   "description": "Daktronics AllSport CG"
  },
  {
   "id": 5,
   "description": "Daktronics Public"
  },
  {
   "id": 11,
   "description": "Elak Emk"
  },
  {
   "id": 4,
   "description": "ElectroMech V2"
  },
  {
   "id": 59,
   "description": "ESK"
  },
  {
   "id": 19,
   "description": "Eversan"
  },
  {
   "id": 34,
   "description": "Eversan Model 9364"
  },
  {
   "id": 35,
   "description": "Eversan Model 9775"
  },
  {
   "id": 27,
   "description": "Eversan V2"
  },
  {
   "id": 2,
   "description": "Fairplay"
  },
  {
   "id": 7,
   "description": "Fairplay MP69"
  },
  {
   "id": 56,
   "description": "Fairplay MP70"
  },
  {
   "id": 150,
   "description": "FairPlay MP80 Wireless"
  },
  {
   "id": 22,
   "description": "Fairplay Proline"
  },
  {
   "id": 30,
   "description": "FarmTek"
  },
  {
   "id": 33,
   "description": "Favero"
  },
  {
   "id": 71,
   "description": "Fujitsu"
  },
  {
   "id": 32,
   "description": "Funtronix AutoDetect"
  },
  {
   "id": 73,
   "description": "Grunewald"
  },
  {
   "id": 46,
   "description": "HamiltonDigital"
  },
  {
   "id": 13,
   "description": "Harris Time"
  },
  {
   "id": 113,
   "description": "Harris Time V2"
  },
  {
   "id": 62,
   "description": "ICast"
  },
  {
   "id": 37,
   "description": "LGR"
  },
  {
   "id": 45,
   "description": "MacFinish"
  },
  {
   "id": 26,
   "description": "Major Display"
  },
  {
   "id": 28,
   "description": "Mondo"
  },
  {
   "id": 31,
   "description": "Nautronic"
  },
  {
   "id": 57,
   "description": "Nautronic NG 08"
  },
  {
   "id": 3,
   "description": "Nevco"
  },
  {
   "id": 63,
   "description": "NisaSport"
  },
  {
   "id": 39,
   "description": "Nisasport TV"
  },
  {
   "id": 9,
   "description": "OES"
  },
  {
   "id": 44,
   "description": "PannoneScore"
  },
  {
   "id": 38,
   "description": "Prospecta"
  },
  {
   "id": 70,
   "description": "Quince"
  },
  {
   "id": 43,
   "description": "Scoretec"
  },
  {
   "id": 36,
   "description": "Skorled"
  },
  {
   "id": 64,
   "description": "Spectrum MS250"
  },
  {
   "id": 17,
   "description": "Spectrum V2"
  },
  {
   "id": 16,
   "description": "Spectrum V2E"
  },
  {
   "id": 12,
   "description": "Spectrum V2W"
  },
  {
   "id": 0,
   "description": "SportzCastSbData"
  },
  {
   "id": 40,
   "description": "Stramatel"
  },
  {
   "id": 68,
   "description": "Stramatel BE04030"
  },
  {
   "id": 20,
   "description": "Swiss Timing"
  },
  {
   "id": 41,
   "description": "Swiss Timing TP"
  },
  {
   "id": 21,
   "description": "Tissot"
  },
  {
   "id": 67,
   "description": "Trackman"
  },
  {
   "id": 65,
   "description": "UltraScore"
  },
  {
   "id": 42,
   "description": "Uno"
  },
  {
   "id": 8,
   "description": "Varsity"
  },
  {
   "id": 23,
   "description": "Varsity Gen2"
  },
  {
   "id": 55,
   "description": "View All"
  },
  {
   "id": 53,
   "description": "Virtual Bot"
  },
  {
   "id": 58,
   "description": "Westerstrand Basic 200"
  },
  {
   "id": 54,
   "description": "Westerstrand Basic 250"
  }
 ],
 "sports": {
  "1": [
   {
    "id": 39,
    "description": "Daktronics 1600 Baseball"
   },
   {
    "id": 181,
    "description": "Daktronics 1600 Football"
   },
   {
    "id": 76,
    "description": "Daktronics 2000 Rodeo"
   },
   {
    "id": 178,
    "description": "Daktronics 2000 Waterpolo"
   },
   {
    "id": 196,
    "description": "Daktronics 3000 Baseball"
   },
   {
    "id": 180,
    "description": "Daktronics 3000 Football"
   },
   {
    "id": 98,
    "description": "Daktronics 5500 Basketball"
   },
   {
    "id": 115,
    "description": "Daktronics 5500 Volleyball"
   },
   {
    "id": 29,
    "description": "Daktronics Auto Detect"
   },
   {
    "id": 1,
    "description": "Daktronics Baseball"
   },
   {
    "id": 183,
    "description": "Daktronics Baseball Code 5601"
   },
   {
    "id": 404,
    "description": "Daktronics Baseball Pitch Clock"
   },
   {
    "id": 402,
    "description": "Daktronics Baseball Pitch Speed"
   },
   {
    "id": 3,
    "description": "Daktronics Basketball"
   },
   {
    "id": 182,
    "description": "Daktronics Basketball Code 9122"
   },
   {
    "id": 2,
    "description": "Daktronics Football"
   },
   {
    "id": 403,
    "description": "Daktronics Football Code 6103"
   },
   {
    "id": 18,
    "description": "Daktronics Hockey"
   },
   {
    "id": 400,
    "description": "Daktronics Hockey Code 4103"
   },
   {
    "id": 193,
    "description": "Daktronics Hockey Code 9405"
   },
   {
    "id": 179,
    "description": "Daktronics JVC Practice Football"
   },
   {
    "id": 22,
    "description": "Daktronics Lacrosse"
   },
   {
    "id": 401,
    "description": "Daktronics Lacrosse Code 4103"
   },
   {
    "id": 184,
    "description": "Daktronics Min Sec Timer Code 8601"
   },
   {
    "id": 23,
    "description": "Daktronics Soccer"
   },
   {
    "id": 4,
    "description": "Daktronics Softball"
   },
   {
    "id": 77,
    "description": "Daktronics Swimming"
   },
   {
    "id": 26,
    "description": "Daktronics Volleyball"
   },
   {
    "id": 19,
    "description": "Daktronics Wrestling"
   }
  ],
  "2": [
   {
    "id": 604,
    "description": "Fairplay Baseball Code 30"
   },
   {
    "id": 6,
    "description": "Fairplay Baseball Code 31"
   },
   {
    "id": 123,
    "description": "Fairplay Baseball Code 32"
   },
   {
    "id": 122,
    "description": "Fairplay Baseball Code 33"
   },
   {
    "id": 58,
    "description": "Fairplay Baseball Code 34"
   },
   {
    "id": 59,
    "description": "Fairplay Baseball Code 35"
   },
   {
    "id": 126,
    "description": "Fairplay Basketball Code 0"
   },
   {
    "id": 60,
    "description": "Fairplay Basketball Code 1"
   },
   {
    "id": 68,
    "description": "Fairplay Basketball Code 10"
   },
   {
    "id": 127,
    "description": "Fairplay Basketball Code 11"
   },
   {
    "id": 120,
    "description": "Fairplay Basketball Code 12"
   },
   {
    "id": 121,
    "description": "Fairplay Basketball Code 2"
   },
   {
    "id": 62,
    "description": "Fairplay Basketball Code 4"
   },
   {
    "id": 8,
    "description": "Fairplay Basketball Code 5"
   },
   {
    "id": 63,
    "description": "Fairplay Basketball Code 6"
   },
   {
    "id": 61,
    "description": "Fairplay Basketball Code 9"
   },
   {
    "id": 64,
    "description": "Fairplay Football Code 23"
   },
   {
    "id": 5,
    "description": "Fairplay Football Code 24"
   },
   {
    "id": 601,
    "description": "Fairplay Football Code 25"
   },
   {
    "id": 602,
    "description": "Fairplay Football Code 26"
   },
   {
    "id": 603,
    "description": "Fairplay Football Code 27"
   },
   {
    "id": 607,
    "description": "Fairplay Hockey Code 13"
   },
   {
    "id": 125,
    "description": "Fairplay Hockey Code 14"
   },
   {
    "id": 56,
    "description": "Fairplay Lacrosse Code 21"
   },
   {
    "id": 57,
    "description": "Fairplay Soccer Code 22"
   },
   {
    "id": 124,
    "description": "Fairplay Soccer Code 36"
   },
   {
    "id": 7,
    "description": "Fairplay Softball Code 31"
   },
   {
    "id": 606,
    "description": "Fairplay Volleyball Code 0"
   },
   {
    "id": 605,
    "description": "Fairplay Volleyball Code 4"
   }
  ],
  "3": [
   {
    "id": 40,
    "description": "Nevco Baseball"
   },
   {
    "id": 185,
    "description": "Nevco Baseball Code 673"
   },
   {
    "id": 169,
    "description": "Nevco Baseball Code 925"
   },
   {
    "id": 42,
    "description": "Nevco Basketball"
   },
   {
    "id": 70,
    "description": "Nevco Basketball Model 2745"
   },
   {
    "id": 41,
    "description": "Nevco Football"
   },
   {
    "id": 47,
    "description": "Nevco Football Code 827"
   },
   {
    "id": 186,
    "description": "Nevco Handheld Baseball Code 673"
   },
   {
    "id": 44,
    "description": "Nevco Hockey"
   },
   {
    "id": 170,
    "description": "Nevco MPC7 Baseball"
   },
   {
    "id": 171,
    "description": "Nevco MPC7 Basketball"
   },
   {
    "id": 176,
    "description": "Nevco MPC7 Basketball Code 1"
   },
   {
    "id": 49,
    "description": "Nevco MPC7 Football"
   },
   {
    "id": 173,
    "description": "Nevco MPC7 Football Code 1"
   },
   {
    "id": 751,
    "description": "Nevco MPC7 Hockey"
   },
   {
    "id": 177,
    "description": "Nevco MPC7 Lacrosse"
   },
   {
    "id": 172,
    "description": "Nevco MPC7 Volleyball"
   },
   {
    "id": 752,
    "description": "Nevco MPCX Baseball Code 252"
   },
   {
    "id": 750,
    "description": "Nevco MPCX Baseball Code 706"
   },
   {
    "id": 175,
    "description": "Nevco MPCX Soccer"
   },
   {
    "id": 45,
    "description": "Nevco Soccer"
   },
   {
    "id": 69,
    "description": "Nevco Soccer Code 761"
   },
   {
    "id": 46,
    "description": "Nevco Volleyball"
   },
   {
    "id": 48,
    "description": "Nevco Wrestling"
   }
  ],
  "4": [
   {
    "id": 160,
    "description": "Electro-Mech 14X_15X Baseball"
   },
   {
    "id": 9,
    "description": "Electro-Mech Baseball"
   },
   {
    "id": 11,
    "description": "Electro-Mech Basketball"
   },
   {
    "id": 13,
    "description": "Electro-Mech Basketball Swapped Teams"
   },
   {
    "id": 10,
    "description": "Electro-Mech Football"
   },
   {
    "id": 135,
    "description": "Electro-Mech Hockey"
   },
   {
    "id": 67,
    "description": "Electro-Mech LS Baseball"
   },
   {
    "id": 165,
    "description": "Electro-Mech LX Baseball"
   },
   {
    "id": 95,
    "description": "Electro-Mech LX Hockey"
   },
   {
    "id": 99,
    "description": "Electro-Mech LX Lacrosse"
   },
   {
    "id": 66,
    "description": "Electro-Mech LX Soccer"
   },
   {
    "id": 65,
    "description": "Electro-Mech Soccer"
   },
   {
    "id": 12,
    "description": "Electro-Mech Softball"
   },
   {
    "id": 136,
    "description": "Electro-Mech Volleyball"
   }
  ]
 },
 "configurations": {
  "1": [
   {
    "id": 11,
    "description": "Wired",
    "requiredAdditionalFields": [],
    "specialInstructions": []
   },
   {
    "id": 12,
    "description": "Wireless",
    "requiredAdditionalFields": [
     "Group (BCAST, 0 - 8)",
     "Channel (CHAN, 0 - 8)",
     "ExternalAntenna (True - False)"
    ],
    "specialInstructions": []
   }
  ],
  "2": [
   {
    "id": 23,
    "description": "Wired",
    "requiredAdditionalFields": [],
    "specialInstructions": []
   }
  ],
  "3": [
   {
    "id": 36,
    "description": "Wired",
    "requiredAdditionalFields": [],
    "specialInstructions": []
   }
  ],
  "4": [
   {
    "id": 17,
    "description": "Wired",
    "requiredAdditionalFields": [],
    "specialInstructions": []
   },
   {
    "id": 18,
    "description": "Wireless",
    "requiredAdditionalFields": [
     "Channel (Channel, 0 - 255)",
     "ExternalAntenna"
    ],
    "specialInstructions": []
   }
  ],
  "150": [
   {
    "id": 26,
    "description": "Wireless",
    "requiredAdditionalFields": [
     "Channel (Group #, 0 - 99)",
     "ExternalAntenna"
    ],
    "specialInstructions": []
   }
  ]
 }
}
