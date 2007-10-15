from genome_feedforward import *
from species import *
#from psyco.classes import *
    
class TournamentSelection:
    ''' Tournament selection with k = 2 '''
    def __init__(self, pop):
        self._pop = pop
    def __call__(self):
        random.shuffle(self._pop)
        s1, s2 = self._pop[0], self._pop[1]
        if s1.fitness >= s2.fitness:
            return s1
        else:
            return s2

class Population:
    ''' Manages all the species  '''
    selection = TournamentSelection
    evaluate = None # Evaluates the entire population. You need to override 
                    # this method in your experiments
    

    def __init__(self, popsize):
        self.__popsize = popsize
        self.__population = [Chromosome.create_fully_connected(Config.input_nodes, Config.output_nodes) \
                             for i in xrange(self.__popsize)]
        self.__species = []
        self.compatibility_threshold = Config.compatibility_threshold
    
    def __len__(self):
        return len(self.__population)
    
    def best(self):
        return max(self.__population)
    
    def __iter__(self):
        return iter(self.__population)
    
    def remove(self, chromo):
        ''' Removes a chromosome from the population '''
        self.__population.remove(chromo)
        
    def __speciate(self):
        """ Group chromosomes into species by similarity """   
        # put best members back to their species
        for c in self:
            for s in self.__species:                
                if c.id == s.representative.id:
                    s.add(c)
                    break
                
        # Remove empty species
        self.__species = [s for s in self.__species if len(s) > 0] 
                    
        # remove each species' representant from population        
        for s in self.__species:
            for c in self:
                if c.id == s.representative.id:
                    self.remove(c)
                    break        
        
        for c in self:
            found = False
            # TODO: if c.species_id is not None try this species first      
            for s in self.__species:                
                if c.distance(s.chromosomes[0]) < self.compatibility_threshold:
                    c.species_id = s.id # the species chromo belongs to
                    s.add(c)                
                    #print 'chromo %s added to species %s' %(chromo.id, s.id)
                    found = True
                    break # we found a compatible species, so let's skip to the next
                
            if not found: # create a new species for this lone chromosome
                self.__species.append(Species(c)) 
                c.species_id = self.__species[-1].id                
                #print 'Creating new species %s and adding chromo %s' %(self.__species[-1].id, c.id)
        
        # controls compatibility threshold
        if len(self.__species) > species_size:
            self.compatibility_threshold += compatibility_change
        elif len(self.__species) < species_size:
            if self.compatibility_threshold > compatibility_change:
                self.compatibility_threshold -= compatibility_change
            else:
                print 'Compatibility threshold cannot be changed (minimum value has been reached)'            
                
    def average_fitness(self):
        ''' Returns the average raw fitness of population '''
        sum = 0.0
        for c in self:
            sum += c.fitness
            
        return sum/len(self)
    
    def __compute_spawn_levels(self):
        """ Compute each species' spawn amount (Stanley, p. 40) """
        
        # 1. boost if young and penalize if old (on raw fitness!) - on average_raw?
        for s in self.__species:
            if s.age < Config.youth_threshold:
                s.boost()
            if s.age > Config.old_threshold:
                s.penalize()                
        
        # 2. Share fitness (only usefull for computing spawn amounts)
        # 3. Compute spawn
        # More about it on: http://tech.groups.yahoo.com/group/neat/message/2203
        
        # Sharing the fitness is only meaningful here  
        # we don't really have to change each individual's raw fitness 
        total_average = 0.0
        for s in self.__species:
                total_average += s.average_fitness()
      
        # average_fitness is being computed twice! optimize!        
        for s in self.__species:
            s.spawn_amount = int(round((s.average_fitness()*self.__popsize/total_average)))
                    
    def epoch(self, n):
        ''' Runs NEAT's genetic algorithm for n epochs. All the speciation methods are handled here '''
        
        for generation in xrange(n):
            print 'Running generation',generation
            
            # Evaluate individuals
            self.evaluate()              
            # Current generation's best chromosome 
            best_chromo = max(self.__population)
            # Current population's average fitness
            avg_pop = self.average_fitness()                              
            # Speciates the population
            self.__speciate()                  
            # Compute spawn levels for each remaining species
            self.__compute_spawn_levels()      

            # Which species has the best chromosome?
            for s in self.__species:
                s.hasBest = False
                if best_chromo.species_id == s.id:
                    s.hasBest = True

            print 'Population\'s average fitness', avg_pop
            print 'Best fitness: %s - size: %s ' %(best_chromo.fitness, best_chromo.size())
            #print best_chromo
            file = open('best','w')
            file.write(str(best_chromo))
            file.close()
           
            # print some "debugging" information
            print 'Species length: %d totalizing %d individuals' %(len(self.__species), sum([len(s) for s in self.__species]))
            print 'Species ID :',[s.id for s in self.__species]
            print 'Each species size:', [len(s) for s in self.__species]
            print 'Amount to spawn:',[s.spawn_amount for s in self.__species]
            print 'Species age:',[s.age for s in self.__species]
            print 'Species imp:',[s.no_improvement_age for s in self.__species] # species no improvement age            
                
            # -------------------------- Producing new offspring -------------------------- #
            new_population = [] # next generation's population
            
            # Spawning new population
            for s in self.__species:
                #print 'Species %s produced %s' %(s.id, len(temp))
                new_population.extend(s.reproduce())
                           
            # Controls under or overflow
            fill = (self.__popsize) - len(new_population)
            if fill < 0: # overflow
                print 'Removing %d excess individual(s) from the new population' %-fill
                # This is dangerous! I can't remove a species' representative!
                new_population = new_population[:fill] # Removing the last added members
                
            if fill > 0: # underflow
                print 'Selecting %d more individual(s) to fill up the new population' %fill
                select = self.selection(self.__population)
                # Apply tournament selection in the whole population (allow inter-species mating?)
                # or select a random species to reproduce?
                for i in range(fill):
                    parent1 = select()
                    parent2 = select() 
                    child = parent1.crossover(parent2)
                    new_population.append(child.mutate());              
                    
            # Updates current population
            assert self.__popsize == len(new_population), 'Different population sizes!'
            self.__population = new_population[:]
            # The new pop hasn't been evaluated at this point! Don't call average_fitness() !
            
            # Remove stagnated species (except if it has the best chromosome)
            self.__species = [s for s in self.__species if \
                              s.no_improvement_age <= max_stagnation or \
                              s.no_improvement_age > max_stagnation and s.hasBest == True]    
        
if __name__ ==  '__main__' :
    
    # sample fitness function
    def eval_fitness(population):
        for chromosome in population:
            chromosome.fitness = 1.0
            
    # set fitness function 
    Population.evaluate = eval_fitness
    
    # creates the population
    pop = Population(50)
    # runs the simulation for 250 epochs
    pop.epoch(250)       

# Things left to check:
# b) boost and penalize is done inside Species.shareFitness() method (as in Buckland's code)
# d) ELE (Extinct Life Events) - something to be implemented as described in NEAT4J version 

# Algorithm:
# 1. Apply fitness sharing in each species
# 2. Compute spawn levels for each species (need to round up or down to an integer value)
# 3. Keep the best performing individual of each species (per species elitism) - if spawn amount >= 1
# 4. Reserve some % members of each species to produce next gen.
#    4.1 Parents are chosen randomly (uniform distribuition with replacement) - this is much like tournament selection with k = len(parents_chosen)
#    4.2 Create offspring based on species's spawn amount:
#        a) If the species has only one member we keep it to the next gen.
#        b) If the species has only one member besides the best we only apply mutation
#        c) Select two parents from the remaining individuals (make sure we do not select the same individuals to mate!)
#           Stanley does not apply tournament selection, but we could try!

# Questions: If a species spawn level is below < 1, what to do? Remove it?
#            When should a species be removed? Before fitness sharing?

# NEAT FAQ: http://www.cs.ucf.edu/~kstanley/neat.html#neatref