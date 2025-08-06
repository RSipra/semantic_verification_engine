


Before diving into any code, I needed a roadmap—something to help me think, develop, and ultimately bring the idea to life. Building a project plan gave me a bird’s-eye view and helped streamline the entire process. I began by clarifying my initial goals:
- Get hands-on with Python OOP and apply it meaningfully.
- Use the project as a playground for data science tools, especially NLP.
- Apply some of the product management concepts I’d been learning -> by building an actual product roadmap.
- Have fun building something real and tangible! :)
- Create something tangible.  and if I could turn NLP into something a pre-teen could play with, it would be the ultimate test of both usability and my understanding of the underlying concepts.

That last point gave the project its personality. My favourite audience is my daughter, f I could turn complex NLP concepts into something a she could play with, it would be the ultimate test of both usability and my own understanding.  Our running game of quizzing each other on obscure Harry Potter facts before bed felt like the perfect inspiration.

#### First draft- sketching the path:

Working backwards from the end goal, a web-based trivia game with smart, semantic answer-checking, I defined a bare-bones MVP and a focused tech stack. This led to the first version of the workflow document, which laid out the project’s stages in four logical phases:

1. Phase 1: Core Game Logic (CLI Foundation)
2. Phase 2: Basic Web App (Flask)
3. Phase 3:  NLP Integration
4. Phase 4: Enhancements 

This initial plan helpme me transform a vague idea into an actionable structure, with sprints to track progress and keep things moving.

Reference: [First draft of the detailed workflow (rev. 0) on Github](https://github.com/RSipra/Harry_Potter_Trivia/blob/main/docs/superceded/Detailed_workflow_rev0.docx)

#### Iterating and refining the roadmap:

The workflow essentially became the roadmap. As Phase 1 unfolded, insights and questions helped me iteratively evolve the plan. This living document became the single source of truth, redrawn and refined as the project continued.

**Evolution 1: Building for quality, not just speed**

I quickly realized that speed alone wasn’t enough. To build something maintainable (and worth including in a portfolio), I had to bake in professional engineering practices early. These additions had two focus areas, first my learning goals to build a fundamental understanding, and second the implementation within the game development. This included:
- [Patterns] Checkpoints: Each sprint now includes points to learn about and consider relevant software design patterns (like Strategy or Facade). This will help keep the codebase flexible and future-proof.
- [Testing] and Deployment. The most significant change was to create Phase 1.5 for Deployment, Testing & Refinement. Even though i knew this would slow down progress on new features but having a solid base was critical. I scheduled time to learn pytest, increase test coverage, and even plan for user testing and containerization with Docker. This was a proactive move to reduce technical debt before it got out of hand.

**Evolution 2: Reprioritizing around the core value (NLP)**

Initially, the roadmap placed the web app development before the NLP integration. But I took a step back and re-evaluated. The real showcase here is the data science.

So I flipped the order. I brought the NLP work forward, prototyping the hybrid answer-checker and building the custom NER model. The architectural refactoring to support the web app could come later. This prioritized getting the core data science components built and validated, even if it meant the cleanup would be slightly more complex. It was a conscious decision to put the project's "value proposition" front-and-center.

Reference: [Superceded workflows on GitHub](https://github.com/RSipra/Harry_Potter_Trivia/tree/main/docs/superceded)

#### Current workflow: a living Agile strategy
The current roadmap is the product of that ongoing iteration. It blends structure with flexibility and is guided by the phased-agile mindset: plan, execute, learn, adapt. 

- **Phase 1: Core Game Logic & CLI Foundation:** Start with a solid, tested foundation for the game MVP and the trivia dataset.
- **Phase 2:  NLP Integration (Data Augmentation & Semantic Features) & Architectural Refinement**. Dive into the heart of the project using NLP to build semantic features such as:
    - a hybrid answer-checking pipeline using fuzzy matching, NER, and sentence embeddings tailored by question type, 
    - a custom offline NER tagging model for richer context-aware categorization.
- **Phase 3: Web Application & Deployment**. Build the user-facing version and prep for deployment.
- **Phase 4: Future Enhancements & Moonshots**. Consider ideas for enhancements and includes some ambitious "moonshot" goals.

This status of the project is tracked in the [Project timeline section](link) below. Refer to that section for more information.

Reference: [Detailed Workflow Document (rev.3) on GitHub](https://github.com/RSipra/Harry_Potter_Trivia/blob/main/docs/Overall%20workflow/Detailed_workflow_rev3.md) 