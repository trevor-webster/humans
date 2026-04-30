# research question
- many stories on humans,
  - is there a familiar or basic human plot 
  - what are the different stories, getting told, basically

  - **Why** to make sense of all them, big picture, not the time to read them all 


## path sketch
    - progress through the project, follow the decisions made, alt paths not taken, path taken forward

    - to method and how it answers question
    - how concretely the expirement was run using the chosen tool
      - book v book
      - broad cultural background v book
    - results


# Method
## common or different?
  - how do we answer the question
  - to find what stands out as the human narrative,

  - common
    - do same ideas emerge for the humans stories
  - different
    - where do they differ, e.g. same components
  - either way, finding what's common or different asks for comparison

## data
  - concretely, what to compare, datasets

### popular books 
  - selected 10 for human history or anthropology, popular enough to sit on anyone's bookshelf (Sapiens a bestseller)

 #### weakness
  not extensive sample but justification by (zipf, rich-get-richer) argument that most of influence to culture (human story) found in a sample of popular-ish books

### broad cultural baseline corpus
    - WikiText dataset of verified Good and Featured articles
    - probably passes a filter for popularity 
   
#### why not Google Books 
  - not good measure of cultural popularity and biases scientific lit.


## why allotax
  - tool or method that answers How to compare
  - big picture view of how different two systems are, it brings out which components are important to each story, relative to another

### how it answers
  - visually and 
  - quatnifies the  comparison,  what's important to system, traceable to what component was measured; 
  - measurements can be used at scale for further conclusions


## why not, weaknesses
  - not looking for an overall measurement of sentiment
    - importance measured in size not sentiment
  - no narrative, no Time captured
    - justification :
      - narrative time, how the author ordered discussion, wasn't the focus
      - can get a picture of story without time; maybe like a logline out of a plot
      - hadn't worked out a **chronological** time method

  - no causality
  - finds what stories are told but doesn't verify authors' claims directly using other disciplines

## How, concretely
  - 3-gram for descriptive power, from inspection
  - \alpha=0 philosophically didn't see it helpful to emphasize function words; 
  - experiment structured in "slices" of comparisons

# Results
  ### book v book slice
    - compare book v book pairs
    - across book "slice" row brings forward the most important components from the story compared to every other
    - the big picture mostly not identical


 ### Wikitext v slice
    - the same cultural background vs books
    - if the stories have commonality it should show
    - what repeats as important across humans stories

  
# Long term
  - capturing storyline over time
  - stories not verified - how supported are stories by citations
  - find some way to mechanically calculate the proximity to try to arrive at the commonalities
  - is there SVD 
  - suggestions?
  

