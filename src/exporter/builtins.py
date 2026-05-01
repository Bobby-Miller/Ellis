BUILTIN_UDTS = [
    {
        "name": "TIMER",
        "members": [
            {"name": "PRE", "data_type": "DINT", "array_dimensions": None},
            {"name": "ACC", "data_type": "DINT", "array_dimensions": None},
            {"name": "EN", "data_type": "BOOL", "array_dimensions": None},
            {"name": "TT", "data_type": "BOOL", "array_dimensions": None},
            {"name": "DN", "data_type": "BOOL", "array_dimensions": None}
        ]
    },
    {
        "name": "COUNTER",
        "members": [
            {"name": "PRE", "data_type": "DINT", "array_dimensions": None},
            {"name": "ACC", "data_type": "DINT", "array_dimensions": None},
            {"name": "CU", "data_type": "BOOL", "array_dimensions": None},
            {"name": "CD", "data_type": "BOOL", "array_dimensions": None},
            {"name": "DN", "data_type": "BOOL", "array_dimensions": None},
            {"name": "OV", "data_type": "BOOL", "array_dimensions": None},
            {"name": "UN", "data_type": "BOOL", "array_dimensions": None}
        ]
    },
    {
        "name": "CONTROL",
        "members": [
            {"name": "LEN", "data_type": "DINT", "array_dimensions": None},
            {"name": "POS", "data_type": "DINT", "array_dimensions": None},
            {"name": "EN", "data_type": "BOOL", "array_dimensions": None},
            {"name": "EU", "data_type": "BOOL", "array_dimensions": None},
            {"name": "DN", "data_type": "BOOL", "array_dimensions": None},
            {"name": "EM", "data_type": "BOOL", "array_dimensions": None},
            {"name": "ER", "data_type": "BOOL", "array_dimensions": None},
            {"name": "UL", "data_type": "BOOL", "array_dimensions": None},
            {"name": "IN", "data_type": "BOOL", "array_dimensions": None},
            {"name": "FD", "data_type": "BOOL", "array_dimensions": None}
        ]
    },
    {
        "name": "MESSAGE",
        "members": [
            {"name": "ERR", "data_type": "DINT", "array_dimensions": None},
            {"name": "EN", "data_type": "BOOL", "array_dimensions": None},
            {"name": "ST", "data_type": "BOOL", "array_dimensions": None},
            {"name": "DN", "data_type": "BOOL", "array_dimensions": None},
            {"name": "ER", "data_type": "BOOL", "array_dimensions": None},
            {"name": "EW", "data_type": "BOOL", "array_dimensions": None}
        ]
    },
    {
        "name": "CONNECTION_STATUS",
        "members": [
            {"name": "RunMode", "data_type": "BOOL", "array_dimensions": None},
            {"name": "ConnectionFaulted", "data_type": "BOOL", "array_dimensions": None}
        ]
    },
    {
        "name": "PID",
        "members": [
            {"name": "SP", "data_type": "REAL", "array_dimensions": None},
            {"name": "KP", "data_type": "REAL", "array_dimensions": None},
            {"name": "KI", "data_type": "REAL", "array_dimensions": None},
            {"name": "KD", "data_type": "REAL", "array_dimensions": None},
            {"name": "BIAS", "data_type": "REAL", "array_dimensions": None},
            {"name": "MAXS", "data_type": "REAL", "array_dimensions": None},
            {"name": "MINS", "data_type": "REAL", "array_dimensions": None},
            {"name": "DB", "data_type": "REAL", "array_dimensions": None},
            {"name": "SO", "data_type": "REAL", "array_dimensions": None},
            {"name": "MAXI", "data_type": "REAL", "array_dimensions": None},
            {"name": "MINI", "data_type": "REAL", "array_dimensions": None},
            {"name": "UPD", "data_type": "REAL", "array_dimensions": None},
            {"name": "OUT", "data_type": "REAL", "array_dimensions": None},
            {"name": "PV", "data_type": "REAL", "array_dimensions": None},
            {"name": "ERR", "data_type": "REAL", "array_dimensions": None},
            {"name": "OUT", "data_type": "REAL", "array_dimensions": None}
        ]
    }
]
