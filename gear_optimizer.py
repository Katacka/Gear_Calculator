# TODO:
#   Whitelist/blacklist specific tiers
#   Visualize optimality with graphs
#   Return N most optimal loadouts instead of logging "new" optimums
#   Implement MiniMax
#   Fix skip_weapon

import json
import argparse
import itertools

##
# Item data wrapper
##
class Item:
    def __init__(self, item):
        self.name = item["name"]
        self.data = item["data"]


##
# Stores information concerning a player's item loadout
##
class Gear:
    def __init__(self, loadout):
        for item in loadout:
            setattr(self, item["type"], Item(item))

    def __iter__(self):
        for var in vars(self).items():
            yield var


##
# Determines the optimum item loadout given user supplied goals/constraints
##
class Optimizer:
    def __init__(self, args):
        with open(args.filename) as raw_items:
            self.items = json.load(raw_items)

        self.whitelist = args.whitelist #TODO convert white/black lists to one list with '+'/'-' support
        self.blacklist = args.blacklist
        self.item_types = args.item_types #TODO - Create/Annotate data
        self.item_tiers = args.item_tiers #TODO - Create/Annotate data
        self.type_scaling = args.scaling
        self.expected_damage = args.expected_damage
        self.skip_weapon = args.skip_weapon
        self.verbose = args.verbose

    ##
    # Iterates across all combinations of items to determine optimum groupings #TODO - Implement MiniMax alg
    ##
    def optimize_gear(self):
        gear_list = self.generate_gear_list()

        prev_score = 0
        for item_loadout in itertools.product(*gear_list):
            gear = Gear(item_loadout)
            reduction_data = self.calc_damage_reduction(gear)
            reduction_score = self.calc_reduction_score(reduction_data, gear)

            if reduction_score >= prev_score:
                prev_score = reduction_score
                self.print_results(reduction_data, gear)

    ##
    # Generates a list including items for all valid types/tiers
    ##
    def generate_gear_list(self):
        gear_list = []
        for type in self.item_types:
            if type == "weapon" and self.skip_weapon:
                continue

            type_list = []
            for item_name in self.items[type]:
                if self.legal_item(item_name):
                    item = self.items[type][item_name]
                    type_list.append({"type": type, "name": item_name, "data": item})

            if type_list:
                gear_list.append(type_list)
        return gear_list

    ##
    # Determines whether {@param item} is in self.whitelist (if it exists)
    #   and not in self.blacklist (if it exists)
    #
    # Parameters:
    #   item - A dictionary containing item data
    #
    # Return:
    #   legal_item - A boolean describing whether {@param item} is legal
    ##
    def legal_item(self, item):
        try:
            legal_name = not item in self.blacklist and (not self.whitelist or item in self.whitelist)
            legal_type = True or item["type"] in self.item_types #TODO - Add proper item data
            legal_tier = True or item["tier"] in self.item_tiers #TODO - Add proper item data
        except KeyError:
            return false
        return legal_name and legal_type and legal_tier

    ##
    # Calculates damage reduction percentages for the contextual {@param gear}
    #
    # Parameters:
    #   gear - A Gear object describing the player's current loadout
    #
    # Return:
    #   reduction_data - A dict of float values describing the percentage of
    #     damage reduced from various contexts (i.e. projectile_protection)
    ##
    def calc_damage_reduction(self, gear):
        # Generic attributes
        protection = self.get_property_sum("protection", gear)
        armor = self.get_property_sum("armor", gear)
        toughness = self.get_property_sum("armor_t", gear)
        evasion = self.get_property_sum("evasion", gear)

        # Specific attributes
        proj_protection = self.get_property_sum("proj_protection", gear)
        blast_protection = self.get_property_sum("blast_protection", gear)
        fire_protection = self.get_property_sum("fire_protection", gear)
        feather_falling = self.get_property_sum("feather_falling", gear)
        ability_evasion = self.get_property_sum("ability_evasion", gear)
        melee_evasion = self.get_property_sum("melee_evasion", gear)

        # Generic reduction percents
        reduction_data = {}
        reduction_data["protection"] = self.calc_protection_reduction(protection)
        reduction_data["armor"] = self.calc_armor_reduction(armor, toughness)
        reduction_data["evasion"] = self.calc_evasion_reduction(evasion)
        reduction_data["general"] = self.calc_general_reduction(reduction_data["protection"], reduction_data["armor"], reduction_data["evasion"])
        reduction_data["true_effective_health"] = self.calc_effective_health(reduction_data["general"], gear)

        # Specific reduction percents
        reduction_data["projectile"] = self.calc_spec_protection_reduction(protection, proj_protection)
        reduction_data["blast"] = self.calc_spec_protection_reduction(protection, blast_protection)
        reduction_data["fire"] = self.calc_spec_protection_reduction(protection, fire_protection)
        reduction_data["feather_falling"] = self.calc_spec_protection_reduction(protection, feather_falling)
        reduction_data["ability"] = self.calc_spec_evasion_reduction(evasion, ability_evasion)
        reduction_data["melee"] = self.calc_spec_evasion_reduction(evasion, melee_evasion)

        return reduction_data

    def get_property_sum(self, property, gear):
        sum = 0
        for key, item in gear:
            try:
                sum += float(item.data[property])
            except KeyError:
                continue
        return sum

    def calc_general_reduction(self, *reductions):
        if len(reductions) == 0:
            return 0

        damage = 1
        for r in reductions:
            damage *= (1 - r)
        return 1 - damage

    def calc_protection_reduction(self, protection):
        return min(protection * 0.04, 0.8)

    def calc_armor_reduction(self, armor, toughness):
        return min(20, max(armor / 5, armor - (self.expected_damage / (2 + (toughness / 4))))) / 25

    def calc_evasion_reduction(self, evasion):
        return min((evasion // 5) * 0.2, 0.8) #TODO - Rework evasion calc to include second_wind and more intelligent thresholds

    def calc_effective_health(self, reduction, gear):
        health = 20 + self.get_property_sum("health", gear)
        health *= 1 + self.get_property_sum("health_p", gear)
        return health * (1 / (1 - reduction))

    def calc_spec_protection_reduction(self, protection, spec):
        return self.calc_protection_reduction(protection + spec * 2)

    def calc_spec_evasion_reduction(self, evasion, spec):
        return self.calc_evasion_reduction(evasion + spec * 2)

    ##
    # Returns #TODO - Finish
    #
    ##
    def calc_reduction_score(self, reduction_data, gear):
        reduction_data["scaled_protection"] = self.scale_reduction_type(reduction_data, ["projectile", "fire", "blast", "feather_falling"], "protection")
        reduction_data["scaled_armor"] = self.scale_reduction_type(reduction_data, [], "armor")
        reduction_data["scaled_evasion"] = self.scale_reduction_type(reduction_data, ["ability", "melee"], "evasion")

        reduction_data["score"] = self.calc_general_reduction(reduction_data["scaled_protection"],
                                                              reduction_data["scaled_armor"], reduction_data["scaled_evasion"])
        reduction_data["scaled_effective_health"] = self.calc_effective_health(reduction_data["score"], gear)
        return reduction_data["scaled_effective_health"]

    def scale_reduction_type(self, reduction_data, damage_types, category):
        scaled_reduction = 0.0
        total_scale = 1.0
        for type in damage_types:
            if type in self.type_scaling:
                 scale = self.type_scaling[type]
                 scaled_reduction += (reduction_data[type] * float(scale))
                 total_scale -= float(scale)
        scaled_reduction += reduction_data[category] * total_scale
        return scaled_reduction

    def print_results(self, reduction_data, gear):
        # Expected stats - based off averaged scalings
        print("Scaled Effective Health: " + str(reduction_data["scaled_effective_health"]))
        print("Scaled Reduction: " + str(reduction_data["score"]) + "\n")

        # Guarenteed stats - based off generic reductions
        print("Effective Health: " + str(reduction_data["true_effective_health"]))
        print("Damage Reduction: " + str(reduction_data["general"]) + "\n")

        # Print item names
        for type, item in gear:
            print(type.capitalize() + ": " + str(item.name))
            if self.verbose:
                # Print item attributes
                print("    " + str(item.data))
        print("\n\n")


def parse_arguments():
    parser = argparse.ArgumentParser(description="Analyze Monumenta r2 loadout optimalities")
    parser.add_argument("--filename", type=str, default="items.json", help="Defines the contextual item data for the optimality search")
    parser.add_argument("--whitelist", type=list, default=None, help="Only include these items in the optimality search") #TODO - Implement
    parser.add_argument("--blacklist", type=list, default=[], help="A list of items to exclude from the optimality search")
    parser.add_argument("--item_types", type=list, default=["boots", "legs", "chest", "head", "offhand", "weapon"], help="Only include these item types in the optimality search")
    parser.add_argument("--item_tiers", type=list, default=[1, 2, 3, 4, 5, "uncommon", "unique", "rare", "artifact", "relic", "epic"], help="Only include these item tiers in the optimality search")
    parser.add_argument("--scaling",  action = type('', (argparse.Action, ), dict(__call__ = lambda a, p, n, v, o: getattr(n, a.dest).update(dict([v.split('=')])))), default = {}, help="A dictionary of damage reduction types (i.e. projectile_protection) to decimal scalings." +
                        "For instance, if projectile=0.5 is input, the protection category will give equal consideration (50-50) to projectile_protection and protection")
    parser.add_argument("--expected_damage", type=float, default=20, help="Expected 'maximum' damage from mobs. Used for effective armor calculations")
    parser.add_argument("--skip_weapon", type=bool, default=True, help="Determines whether mainhand weapon combinations should be considered")
    parser.add_argument("--verbose", type=bool, default=True, help="Determines whether item attribute information should be printed (i.e. armor values)")
    return parser.parse_args()

# Main
args = parse_arguments()
opt = Optimizer(args)
opt.optimize_gear()
