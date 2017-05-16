import const

gridDistance = 500000
planetDistance = 10000000

# colossal - 289546
# enormous - 289416
# large - 289412
# medium - 112356
# small - 112355
groupGravics = [289546, 289416, 289412, 112356, 112355]

# thick blue
groupIce = [288578]

# --
# 450 - Arkonor
# 451 - Bistot
# 452 - Crokite
# 453 - Dark Ochre
# 454 - Hedbergite
# 455 - Hemorphite
# 456 - Jaspet
# 457 - Kernite
# 458 - Plagioclase
# 459 - Pyroxeres
# 460 - Scordite
# 461 - Spodumain
# 462 - Veldspar
# 467 - Gneiss
# 468 - Mercoxit
# 469 - Omber
groupsOre = [450, 451, 452, 453, 454, 455, 456, 457, 458, 459, 460, 461, 462, 467, 469]

typesOre = [22, 17425, 17426,
            1223, 17428, 17429,
            1225, 17432, 17433,
            1232, 17436, 17437,
            21, 17440, 17441,
            1231, 17444, 17445,
            1226, 17448, 17449,
            20, 17452, 17453,
            18, 17455, 17456,
            1224, 17459, 17460,
            1228, 17463, 17464,
            19, 17466, 17467,
            1230, 17470, 17471,
            1229, 17865, 17866,
            1227, 17867, 17868
]

typesCompressOre = [28367, 28385, 28387,
                    28388, 28389, 28390,
                    28391, 28392, 28393,
                    28394, 28395, 28396,
                    28400, 28401, 28402,
                    28403, 28404, 28405,
                    28406, 28407, 28408,
                    28409, 28410, 28411,
                    28421, 28422, 28423,
                    28424, 28425, 28426,
                    28427, 28428, 28429,
                    28418, 28419, 28420,
                    28430, 28431, 28432,
                    28397, 28398, 28399,
                    28412, 28413, 28414,
                    28415, 28416, 28417,
                    ]

typesCompressIce = [28433, 28434, 28435, 28436, 28437, 28438, 28439, 28440, 28441, 28442, 28443, 28444]

groupsMercoxit = [468]

typesMercoxit = [11396, 17869, 17870]

# 17975 - Thick Blue Ice
# 16267 - Dark Glitter
# 16266 - Glare Crust
# 16268 - Gelidus
# 16269 - Krystallos
typesIce = [16262, 16263, 16264, 16265, 16266, 16267, 16268, 16269, 17975, 17976, 17977, 17978]

groupMiningLasers = [
    const.groupStripMiner,
    const.groupMiningLaser,
    const.groupFrequencyMiningLaser
]

typesDrone = {'mining': [10246, 10250, 3218],
              'light': [2203, 2205, 2454, 2456, 2464, 2466, 2486, 2488],
              'medium': [21638, 24640, 15508, 15510, 2173, 2175, 2183, 2185]
}

typesNotCompress = typesOre + typesIce + typesMercoxit

typesCompress = typesCompressOre + typesCompressIce

allOre = groupsOre + groupsMercoxit + typesOre + typesMercoxit
allIce = groupIce + typesIce

# TODO: перенести в БД
bad_words = {0:
                 [
                     '', '',
                     '', ''
                 ],
             1:
                 [
                     '',
                     '', '',
                     '', '',
                     '', '', '',
                     '', '',
                     '', '',
                     ''
                 ]
}

# TODO: перенести в БД
good_words = ['clr', 'status', '?', 'clear', ' plz ', ' pls ']



