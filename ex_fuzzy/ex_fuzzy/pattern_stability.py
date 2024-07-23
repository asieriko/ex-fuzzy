'''
A module to analyze the stability of the patterns generated by the fuzzy classifier. It runs the same experiment n times and then it counts the number of unique patterns that appear in the rule base and how often they do. It also counts the number of times each variable is used in the rule base.
'''
import numpy as np
from multiprocessing.pool import ThreadPool
from pymoo.core.problem import StarmapParallelization
from sklearn.model_selection import train_test_split
import matplotlib.pyplot as plt
from matplotlib import colormaps

try:
    from . import fuzzy_sets as fs
    from . import maintenance as mnt
    from . import rules as rl
    from . import evolutionary_fit as evf
    from . import vis_rules
    from . import eval_rules as evr
    
except:
    import fuzzy_sets as fs
    import maintenance as mnt
    import rules as rl
    import evolutionary_fit as evf
    import vis_rules
    import eval_rules as evr


def add_dicts(dict1: dict, dict2: dict):
    # We will add the values of dict2 to dict1
    for key in dict2:
        try:
            dict1[key] += dict2[key]
        except KeyError:
            dict1[key] = dict2[key]
    
    return dict1

def concatenate_dicts(dict1: dict, dict2: dict):
    # We will concatenate the values of dict2 to dict1
    for key in dict2:
        try:
            dict1[key]
        except KeyError:
            dict1[key] = dict2[key]
    
    return dict1


def str_rule_as_list(rule:str):
    # We will transform the string form of a rule into a list of integers
    rule = rule.replace('[', '')
    rule = rule.replace(']', '')
    rule = rule.replace('(', '')
    rule = rule.replace(')', '')
    rule = rule.replace('.', '')
    
    rule = rule.split()

    return [int(rr) for rr in rule]


class pattern_stabilizer():

    def __init__(self,  X, y, nRules: int = 30, nAnts: int = 4, fuzzy_type: fs.FUZZY_SETS = fs.FUZZY_SETS.t1, tolerance: float = 0.0, class_names: list[str] = None,
                 n_linguistic_variables: int = 3, verbose=False, linguistic_variables: list[fs.fuzzyVariable] = None,
                 domain: list[float] = None, n_class: int=None, runner: int=1) -> None:
        
        '''
        Inits the optimizer with the corresponding parameters.

        :param nRules: number of rules to optimize.
        :param nAnts: max number of antecedents to use.
        :param fuzzy type: FUZZY_SET enum type in fuzzy_sets module. The kind of fuzzy set used.
        :param tolerance: tolerance for the dominance score of the rules.
        :param n_linguist_variables: number of linguistic variables per antecedent.
        :param verbose: if True, prints the progress of the optimization.
        :param linguistic_variables: list of fuzzyVariables type. If None (default) the optimization process will init+optimize them.
        :param domain: list of the limits for each variable. If None (default) the classifier will compute them empirically.
        :param n_class: names of the classes in the problem. If None (default) the classifier will compute it empirically.
        :param precomputed_rules: MasterRuleBase object. If not None, the classifier will use the rules in the object and ignore the conflicting parameters.
        :param runner: number of threads to use. If None (default) the classifier will use 1 thread.
        '''
        self.nRules = nRules
        self.nAnts = nAnts
        self.nclasses_ = n_class

        if not (class_names is None):
            if isinstance(class_names, np.ndarray):
                self.classes_names = list(class_names)
            else:
                self.classes_names = class_names
        else:
            self.classes_names = class_names

        self.custom_loss = None
        self.verbose = verbose
        self.tolerance = tolerance
        

        if runner > 1:
            pool = ThreadPool(runner)
            self.thread_runner = StarmapParallelization(pool.starmap)
        else:
            self.thread_runner = None
        
        if linguistic_variables is not None:
            # If the linguistic variables are precomputed then we act accordingly
            self.lvs = linguistic_variables
            self.n_linguist_variables = [len(lv.linguistic_variable_names()) for lv in self.lvs]
            self.domain = None
            self.fuzzy_type = self.lvs[0].fuzzy_type()
        else:
            # If not, then we need the parameters sumistered by the user.
            self.lvs = None
            self.fuzzy_type = fuzzy_type
            self.n_linguist_variables = n_linguistic_variables
            self.domain = domain

        self.alpha_ = 0.0
        self.beta_ = 0.0

        self.X = X
        self.y = y


    def generate_solutions(self, n=30):
        # We will generate n solutions and return the rule bases and the accuracies
        rule_bases = []
        accs = []

        for ix in range(n):
            fl_classifier = evf.BaseFuzzyRulesClassifier(nRules=10, linguistic_variables=self.lvs, nAnts=3, n_linguistic_variables=5, fuzzy_type=self.fuzzy_type, verbose=False, tolerance=0.01, runner=1)
            # Generate train test partition
            
            X_train, X_test, y_train, y_test = train_test_split(self.X, self.y, test_size=0.33, random_state=ix)
            fl_classifier.fit(X_train, np.array(y_train), n_gen=10, pop_size=10, checkpoints=0)

            rule_bases.append(fl_classifier.rule_base)
            accuracy = np.mean(np.equal(fl_classifier.forward(X_test), np.array(y_test)))
            accs.append(accuracy)
        
        return rule_bases, accs
    

    def count_unique_patterns(self, rule_base: rl.RuleBase):
        '''
        We will count the number of unique patterns in the rule base. It will also count the number of times each variable is used in the rule base and the record the dominance score of each pattern.

        :param rule_base: RuleBase object. The rule base to analyze.
        :return unique_patterns: dict. The dictionary with the unique patterns and the number of times they appear.
        :return patterns_ds: dict. The dictionary with the dominance score of each pattern.
        :return var_used: dict. The dictionary with the number of times each variable is used in the rule base.
        '''
        unique_patterns = {}
        patterns_ds = {}
        var_used = {}

        for ix, rule in enumerate(rule_base.get_rulebase_matrix()):
            pattern = str(rule)
            patterns_ds[pattern] = rule_base[ix].score
            if pattern in unique_patterns:
                unique_patterns[pattern] += 1
            else:
                unique_patterns[pattern] = 1

            for jx, var in enumerate(rule):
                try:
                    var_used[jx][var] += 1
                except:
                    try:
                        var_used[jx][var] = 1
                    except:
                        var_used[jx] = {}
                        var_used[jx][var] = 1
        

        
        return unique_patterns, patterns_ds, var_used
    

    def count_unique_patterns_all_classes(self, mrule_base: rl.MasterRuleBase, class_patterns: dict[list] = None, patterns_dss: dict[list] = None, class_vars: dict[list] = None):
        '''
        Counts the number of unique patterns for all classes. It also counts the number of times each variable is used in the rule base and the dominance score of each pattern.

        :param mrule_base: MasterRuleBase object. The rule base to analyze.
        :param class_patterns: dict[list]. The dictionary with the unique patterns for each class. If None, it will be initialized.
        :param patterns_dss: dict[list]. The dictionary with the dominance score of each pattern for each class. If None, it will be initialized.
        :param class_vars: dict[list]. The dictionary with the number of times each variable is used in the rule base for each class. If None, it will be initialized.
        :return class_patterns: dict[list]. The dictionary with the unique patterns for each class.
        :return patterns_dss: dict[list]. The dictionary with the dominance score of each pattern for each class.
        :return class_vars: dict[list]. The dictionary with the number of times each variable is used in the rule base for each class.
        '''
        if class_patterns is None:
            class_patterns = {ix: {} for ix in range(len(mrule_base))}
            class_vars = {}
            for key in range(len(mrule_base)):
                class_vars[key] = {}
                for jx in range(len(mrule_base.n_linguistic_variables())):
                    class_vars[key][jx] = {zx: 0 for zx in np.arange(-1, mrule_base.n_linguistic_variables()[key])}

            patterns_dss = {ix: {} for ix in range(len(mrule_base))}

        for ix, rule_base in enumerate(mrule_base):
            unique_patterns, patterns_ds, var_used = self.count_unique_patterns(rule_base)
            class_patterns[ix] = add_dicts(class_patterns[ix], unique_patterns)
            for key, value in class_vars.items():
                class_vars[ix][key] = add_dicts(class_vars[ix][key], var_used[key])

            patterns_dss[ix] = concatenate_dicts(patterns_dss[ix], patterns_ds)
            

        return class_patterns, patterns_dss, class_vars
    

    def get_patterns_scores(self, n=30):
        '''
        Gets the patterns scores for the generated solutions.

        :param n: int. The number of solutions to generate.
        :return class_patterns: dict[list]. The dictionary with the unique patterns for each class.
        :return patterns_dss: dict[list]. The dictionary with the dominance score of each pattern for each class.
        :return class_vars: dict[list]. The dictionary with the number of times each variable is used in the rule base for each class.
        :return accuracies: list. The list with the accuracies of the generated solutions.
        :return rule_bases: list. The list with the generated rule bases.
        '''
        rule_bases, accuracies = self.generate_solutions(n)
        self.n = n
        for ix, mrule_base in enumerate(rule_bases):
            if ix == 0:
                class_patterns, patterns_dss, class_vars = self.count_unique_patterns_all_classes(mrule_base)
            else:
                class_patterns, patterns_dss, class_vars = self.count_unique_patterns_all_classes(mrule_base, class_patterns, patterns_dss, class_vars)
            
        # Sort the patterns by the number of appearances
        for ix in range(len(class_patterns)):
            class_patterns[ix] = dict(sorted(class_patterns[ix].items(), key=lambda item: item[1], reverse=True))
            patterns_dss[ix] = dict(sorted(patterns_dss[ix].items(), key=lambda item: item[1], reverse=True))

        return class_patterns, patterns_dss, class_vars, accuracies, rule_bases
    

    def var_reports(self, class_vars: dict, antecedents, cutoff=10):
        '''
        Generates variable reports.
        
        :param class_vars: dict. The dictionary with the number of times each variable is used in the rule base for each class.
        :param antecedents: list. The list of antecedents.
        :param cutoff: int. The number of variables to show in the report.
        '''
        for jx in range(len(class_vars)):
            initiated = False
            sorted_class_ix = dict(sorted(class_vars[jx].items(), key=lambda item: item[1], reverse=True))
            for ix, key in enumerate(sorted_class_ix):
                if key != -1 and sorted_class_ix[key] > 0:
                    if ix > cutoff:
                        break
                    if not initiated:
                        print(f'Variable {antecedents[jx].name}')
                        initiated = True

                    print(f'{antecedents[jx][key].name} appears %.2f times' % float(class_vars[jx][key] / self.n))
            if initiated:
                print()
                

    def text_report(self, class_patterns: dict, patterns_dss: dict, class_vars: dict, accuracies: list, rule_bases: list,
                    rule_cutoff: int = 5):
        '''
        Generates a text report for pattern stability.

        :param class_patterns: dict[list]. The dictionary with the unique patterns for each class.
        :param patterns_dss: dict[list]. The dictionary with the dominance score of each pattern for each class.
        :param class_vars: dict[list]. The dictionary with the number of times each variable is used in the rule base for each class.
        :param accuracies: list. The list with the accuracies of the generated solutions.
        :param rule_bases: list. The list with the generated rule bases.
        :param rule_cutoff: int. The number of rules to show in the report.
        '''
        consequents_names = self.classes_names
        print(f'Pattern stability report for {self.n} generated solutions')
        print('Average accuracy: %.2f\pm%.2f' % (np.mean(accuracies), np.std(accuracies)))
        print('-------------')

        for ix in range(len(class_patterns)):
            class_pattern_ix = class_patterns[ix]
            rules_array_format = [str_rule_as_list(key) for key in class_pattern_ix.keys()]
            patterns_dss_ix = patterns_dss[ix]
            class_vars_ix = class_vars[ix]

            print(f'Class {consequents_names[ix]}')
            print(f'Number of unique patterns: {len(class_pattern_ix)}')
            for jx, rule in enumerate(class_pattern_ix.keys()):
                if jx < rule_cutoff:
                    rule_print_format = rl.generate_rule_string(rules_array_format[jx], rule_bases[ix].antecedents)
                    print(f'Pattern {rule_print_format} appears in %.2f percent of the trials with a Dominance Score of {patterns_dss_ix[str(rule)]}' % float(class_pattern_ix[str(rule)] / self.n))
                else:
                    break
            print()
            self.var_reports(class_vars_ix, rule_bases[0].antecedents)
            print()
    

    def stability_report(self, n=10):
        '''
        Generates a stability report for pattern stabilization.

        :param n: int. The number of solutions to generate.
        :return text_report: str. The text report for pattern stability.
        '''
        class_patterns, patterns_dss, class_vars, accuracies, rule_bases = self.get_patterns_scores(n)
        self.class_patterns = class_patterns
        self.patterns_dss = patterns_dss
        self.class_vars = class_vars
        self.accuracies = accuracies
        self.rule_bases = rule_bases

        return self.text_report(class_patterns, patterns_dss, class_vars, accuracies, rule_bases)
    

    def pie_chart_basic(self, var_ix, class_ix):
        '''
        Generates a pie chart for the variable usage in the rule bases.
        
        :param var_ix: int. The index of the variable to analyze.
        :param class_ix: int. The index of the class to analyze.
        '''
        antecedents = self.rule_bases[0][class_ix].antecedents
        labels = []
        sizes = []
        var = self.class_vars[class_ix][var_ix]

        for key in var.keys():
            if key != -1 and var[key] > 0:
                labels.append(antecedents[key].name)
                sizes.append(var[key])

        fig1, ax1 = plt.subplots()
        ax1.pie(sizes, labels=labels, autopct='%1.1f%%',
                shadow=True, startangle=90)
        ax1.axis('equal')
        plt.show()

    
    def pie_chart_var(self, var_ix):
        '''
        Generates a pie chart for the variable usage in the rule bases.

        :param var_ix: int. The index of the variable to analyze.
        '''
        antecedents = self.rule_bases[0][0].antecedents
        colors = self.gen_colormap(antecedents)

        fig1, ax1 = plt.subplots(ncols=len(self.rule_bases[0]), nrows=1, figsize=(20, 10))
        fig1.suptitle(f'Variable {antecedents[var_ix].name} usage in the rulebases')

        for class_ix in range(len(self.rule_bases[0])):
            labels = []
            sizes = []
            var = self.class_vars[class_ix][var_ix]
            ax1[class_ix].set_title(f'Class {self.classes_names[class_ix]}')
            for key in var.keys():
                if key != -1 and var[key] > 0:
                    labels.append(antecedents[var_ix][key].name)
                    sizes.append(var[key])
        
            ax1[class_ix].pie(sizes, labels=labels, autopct='%1.1f%%', shadow=False, startangle=90, colors=[colors[v] for v in labels])
            ax1[class_ix].axis('equal')

        plt.show()

    
    def pie_chart_class(self, class_ix):
        '''
        Generates a pie chart for the variable usage in the rule bases.

        :param class_ix: int. The index of the class to analyze.
        '''
        antecedents = self.rule_bases[0][0].antecedents
        colors = self.gen_colormap(antecedents)
        
        fig1, ax1 = plt.subplots(ncols=len(self.rule_bases[0]), nrows=1, figsize=(20, 10))
        fig1.suptitle(f'Class {self.classes_names[class_ix]} variable usage in the rulebases')

        for var_ix in range(len(self.rule_bases[0])):
            labels = []
            sizes = []
            var = self.class_vars[class_ix][var_ix]
            ax1[var_ix].set_title(f'Variable {antecedents[var_ix].name}')
            for key in var.keys():
                if key != -1 and var[key] > 0:
                    labels.append(antecedents[var_ix][key].name)
                    sizes.append(var[key])
        
            ax1[var_ix].pie(sizes, labels=labels, autopct='%1.1f%%', shadow=False, startangle=90, colors=[colors[v] for v in labels])
            ax1[var_ix].axis('equal')

        plt.show()

    def gen_colormap(self, antecedents):
        '''
        Generates a colormap for the special cases of 2 and 3 linguistic variables.

        :param antecedents: list. The list of antecedents.
        '''
        largest_vl_ix = np.argmax(self.n_linguist_variables)
        largest_vl_n = self.n_linguist_variables[largest_vl_ix]

        # Note: red and yellow has been softened to avoid eye strain, that's why there are colors specified with hexadecimals
        if largest_vl_n == 2: # There is the special case of low/high
            colors = { label: color  for label, color in zip([antecedent.name for antecedent in antecedents[largest_vl_ix]], ['#FA8072', 'Green'])} 
        elif largest_vl_n == 3: # There is the special case of low/medium/high
            colors = { label: color  for label, color in zip([antecedent.name for antecedent in antecedents[largest_vl_ix]], ['#FA8072', '#EEE8AA', 'Green'])}
        else:
            colormap_custom = list(set([colormaps['coolwarm'](a) for a in len(largest_vl_n)]))
            
            colors = { label: color  for label, color in zip([antecedent.name for antecedent in antecedents], colormap_custom)}
        return colors
            
