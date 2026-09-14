# Changelog

## [0.19.0](https://github.com/jmcvetta/daily-driver/compare/v0.18.2...v0.19.0) (2026-09-11)


### Features

* **constitution:** share the constitution between Claude Code and Omp ([#149](https://github.com/jmcvetta/daily-driver/issues/149)) ([48c5b04](https://github.com/jmcvetta/daily-driver/commit/48c5b04d00cab0060b3c318025e58524d4802bdf))
* **evals:** guard evals-run against an unconfigured judge transport ([#166](https://github.com/jmcvetta/daily-driver/issues/166)) ([a581476](https://github.com/jmcvetta/daily-driver/commit/a58147684f8ef57756bdff90aa75076593b09332))
* **issue-deps:** write the edge and report it, rather than asking first ([#163](https://github.com/jmcvetta/daily-driver/issues/163)) ([980113b](https://github.com/jmcvetta/daily-driver/commit/980113babae60a739bde4350509ba95963755195))
* **issue-labels:** standardize the labels an issue may carry ([#157](https://github.com/jmcvetta/daily-driver/issues/157)) ([e06adfd](https://github.com/jmcvetta/daily-driver/commit/e06adfdbc7cdc6463d8c609281cea7ad5fda6026))
* **omp:** add the thin Oh My Pi runtime adapter ([#145](https://github.com/jmcvetta/daily-driver/issues/145)) ([#150](https://github.com/jmcvetta/daily-driver/issues/150)) ([fbc601c](https://github.com/jmcvetta/daily-driver/commit/fbc601c44638a6dc1ec96b341cd72cfab7bea930))
* **pr-body:** lead the body with the issue it closes ([#165](https://github.com/jmcvetta/daily-driver/issues/165)) ([af8096d](https://github.com/jmcvetta/daily-driver/commit/af8096da56d72346dac67aad3096a104cd667863))
* **skills:** add embark, which works an epic wave by wave ([#162](https://github.com/jmcvetta/daily-driver/issues/162)) ([6c939a7](https://github.com/jmcvetta/daily-driver/commit/6c939a76fb6da46e78ebdcda0f35dc11deb9c818))
* **skills:** add the epic planning skill ([#156](https://github.com/jmcvetta/daily-driver/issues/156)) ([127fbc9](https://github.com/jmcvetta/daily-driver/commit/127fbc90841dabed35a83bad9bc768ef274f10fe))
* **skills:** make the shipped skills portable between Claude Code and Omp ([#155](https://github.com/jmcvetta/daily-driver/issues/155)) ([3bb3e5e](https://github.com/jmcvetta/daily-driver/commit/3bb3e5e24e65b2af7a612213a56fa13de01a7554))


### Bug Fixes

* bump the minor, not the major, before 1.0.0 ([#141](https://github.com/jmcvetta/daily-driver/issues/141)) ([f1a292d](https://github.com/jmcvetta/daily-driver/commit/f1a292deadea7ec229c8e4d6727118491e11e2a8))
* **issue-deps:** name the verified skill:// form for Omp ([#172](https://github.com/jmcvetta/daily-driver/issues/172)) ([a01402b](https://github.com/jmcvetta/daily-driver/commit/a01402b3bce6603d90e528cf5f0169ddb6992ca6))

## [0.18.2](https://github.com/jmcvetta/daily-driver/compare/v0.18.1...v0.18.2) (2026-09-09)


### Bug Fixes

* keep a wake armed while the pull request is open ([#138](https://github.com/jmcvetta/daily-driver/issues/138)) ([d3eb847](https://github.com/jmcvetta/daily-driver/commit/d3eb84723e29c7aa8972e350798a06d73cdec870))

## [0.18.1](https://github.com/jmcvetta/daily-driver/compare/v0.18.0...v0.18.1) (2026-09-09)


### Bug Fixes

* **issue-deps:** pick the client by environment, gh 2.94.0 first ([#133](https://github.com/jmcvetta/daily-driver/issues/133)) ([1ec2d0b](https://github.com/jmcvetta/daily-driver/commit/1ec2d0b285e6e8717874b3d6839da875f3e542a7))
* **undertake:** the ready gate refuses a branch behind its base ([#135](https://github.com/jmcvetta/daily-driver/issues/135)) ([9506f91](https://github.com/jmcvetta/daily-driver/commit/9506f91bc62a1d738d87fefc731722eaf5bb09f5))

## [0.18.0](https://github.com/jmcvetta/daily-driver/compare/v0.17.0...v0.18.0) (2026-09-09)


### Features

* **deps:** bulk dependency upgrades on one branch ([#131](https://github.com/jmcvetta/daily-driver/issues/131)) ([bacec24](https://github.com/jmcvetta/daily-driver/commit/bacec24cfa0bf9ad19f9afdac6249797f75d917c))

## [0.17.0](https://github.com/jmcvetta/daily-driver/compare/v0.16.0...v0.17.0) (2026-09-09)


### Features

* **hooks:** deny the AskUserQuestion widget and ask in chat instead ([#123](https://github.com/jmcvetta/daily-driver/issues/123)) ([601980b](https://github.com/jmcvetta/daily-driver/commit/601980bd4a7add1b20a471b6c97eb375c34f2556))
* **readme:** add the skill for writing tight READMEs ([#128](https://github.com/jmcvetta/daily-driver/issues/128)) ([d4fe333](https://github.com/jmcvetta/daily-driver/commit/d4fe3338d54757d57410daa6d23ae1bd82c23ca5))

## [0.16.0](https://github.com/jmcvetta/daily-driver/compare/v0.15.0...v0.16.0) (2026-09-09)


### Features

* **agents:** retire the four dormant reviewers to the attic ([#120](https://github.com/jmcvetta/daily-driver/issues/120)) ([cbe19f1](https://github.com/jmcvetta/daily-driver/commit/cbe19f1e86c732f3e38589ea4e4500da42f09af7))

## [0.15.0](https://github.com/jmcvetta/daily-driver/compare/v0.14.0...v0.15.0) (2026-09-08)


### Features

* phrase the cost rules as prohibitions, and run the gates on CI ([#116](https://github.com/jmcvetta/daily-driver/issues/116)) ([6ba1be2](https://github.com/jmcvetta/daily-driver/commit/6ba1be261a0bcef3dc10ae35ba76defc5513c64d))
* **undertake:** keep the branch current with master after ready ([#115](https://github.com/jmcvetta/daily-driver/issues/115)) ([10cc2b9](https://github.com/jmcvetta/daily-driver/commit/10cc2b9bf606b89e19adcd6f7dd071b80eddce90))


### Bug Fixes

* **undertake:** check in every two minutes, not every fifteen ([#118](https://github.com/jmcvetta/daily-driver/issues/118)) ([8897c40](https://github.com/jmcvetta/daily-driver/commit/8897c40ae6e1519d5197ba5b8e6e4fdc74404a6c))

## [0.14.0](https://github.com/jmcvetta/daily-driver/compare/v0.13.0...v0.14.0) (2026-09-08)


### Features

* **review-cycle:** wake on pull request events instead of polling for CI ([#112](https://github.com/jmcvetta/daily-driver/issues/112)) ([f3476f9](https://github.com/jmcvetta/daily-driver/commit/f3476f9b70ff6f6c7ab11dbb78ebffa2dea60d03))

## [0.13.0](https://github.com/jmcvetta/daily-driver/compare/v0.12.0...v0.13.0) (2026-09-08)


### Features

* **constitution:** convert the rules to second person imperative ([#108](https://github.com/jmcvetta/daily-driver/issues/108)) ([f3e869b](https://github.com/jmcvetta/daily-driver/commit/f3e869bf2e53cc2990a639441dc23b365f7d33f4))

## [0.12.0](https://github.com/jmcvetta/daily-driver/compare/v0.11.0...v0.12.0) (2026-09-08)


### Features

* **constitution:** give the concision rule a moment, a number and a shape ([#105](https://github.com/jmcvetta/daily-driver/issues/105)) ([c143dd8](https://github.com/jmcvetta/daily-driver/commit/c143dd8572a68104b5ad26e06d6686e6dcbe8c06))
* **conventional-commits-type:** never revert a type the user set ([#104](https://github.com/jmcvetta/daily-driver/issues/104)) ([ea3b80d](https://github.com/jmcvetta/daily-driver/commit/ea3b80deae44049ad89ac83dc1a6ebf558cb5417))

## [0.11.0](https://github.com/jmcvetta/daily-driver/compare/v0.10.0...v0.11.0) (2026-09-08)


### Features

* **constitution:** cut the persona preamble and rename Identity to Voice ([#103](https://github.com/jmcvetta/daily-driver/issues/103)) ([c41eb5a](https://github.com/jmcvetta/daily-driver/commit/c41eb5aba6c2792e3c771c77a5ab38db6717cbe7))

## [0.10.0](https://github.com/jmcvetta/daily-driver/compare/v0.9.0...v0.10.0) (2026-09-08)


### Features

* **review-cycle:** wait for CI by polling the checks, never by sleeping ([#100](https://github.com/jmcvetta/daily-driver/issues/100)) ([6b26d31](https://github.com/jmcvetta/daily-driver/commit/6b26d31cf3520aec4feabfee5775f6d2f1e1535e))

## [0.9.0](https://github.com/jmcvetta/daily-driver/compare/v0.8.0...v0.9.0) (2026-09-08)


### Features

* **review-cycle:** cap the level a rule may select at high ([#94](https://github.com/jmcvetta/daily-driver/issues/94)) ([bb80032](https://github.com/jmcvetta/daily-driver/commit/bb80032059fcb9905ef46ce4a7a562e4b420a7f2))

## [0.8.0](https://github.com/jmcvetta/daily-driver/compare/v0.7.0...v0.8.0) (2026-09-07)


### Features

* **constitution:** drop five sections and the delivery token ([#91](https://github.com/jmcvetta/daily-driver/issues/91)) ([cf8bc8b](https://github.com/jmcvetta/daily-driver/commit/cf8bc8be7c5ef33177e03ab0f69f8b857abed108))
* **undertake:** name the branch in the claim comment ([#92](https://github.com/jmcvetta/daily-driver/issues/92)) ([85e7869](https://github.com/jmcvetta/daily-driver/commit/85e7869bca839dde5146fff2c5abcf0fa0365c4f))

## [0.7.0](https://github.com/jmcvetta/daily-driver/compare/v0.6.0...v0.7.0) (2026-09-07)


### Features

* **constitution:** write in Simplified Technical English ([#82](https://github.com/jmcvetta/daily-driver/issues/82)) ([6ef6bc2](https://github.com/jmcvetta/daily-driver/commit/6ef6bc2f328aee09261b3ac1d92e09d1f0840159))

## [0.6.0](https://github.com/jmcvetta/daily-driver/compare/v0.5.0...v0.6.0) (2026-09-07)


### Features

* **undertake:** claim the issue before the branch is cut ([#79](https://github.com/jmcvetta/daily-driver/issues/79)) ([8354f33](https://github.com/jmcvetta/daily-driver/commit/8354f3391dacfc93d9932d39b3bf1feb86325f31))


### Bug Fixes

* **review-cycle:** name medium, escalate to xhigh, never select max ([#76](https://github.com/jmcvetta/daily-driver/issues/76)) ([1397ad3](https://github.com/jmcvetta/daily-driver/commit/1397ad33b8c1e51c2140e5a73d5aade7c81efa6c))

## [0.5.0](https://github.com/jmcvetta/daily-driver/compare/v0.4.0...v0.5.0) (2026-09-07)


### Features

* **review-cycle:** extract the review-and-answer round from undertake ([#72](https://github.com/jmcvetta/daily-driver/issues/72)) ([103c44b](https://github.com/jmcvetta/daily-driver/commit/103c44b45b6e8d8a7844e20cc319bf6796a8256d))
* **undertake:** open an issue where the work has none ([#71](https://github.com/jmcvetta/daily-driver/issues/71)) ([2d4db15](https://github.com/jmcvetta/daily-driver/commit/2d4db15bad77a1e1cea4006c5ee08e724bc25159))

## [0.4.0](https://github.com/jmcvetta/daily-driver/compare/v0.3.1...v0.4.0) (2026-09-07)


### Features

* **skills:** split the Conventional Commits type decision out of pr-title ([#61](https://github.com/jmcvetta/daily-driver/issues/61)) ([4faae8d](https://github.com/jmcvetta/daily-driver/commit/4faae8d91f6c363c0104325d972b910cbc0476e8))

## [0.3.1](https://github.com/jmcvetta/daily-driver/compare/v0.3.0...v0.3.1) (2026-09-07)


### Bug Fixes

* move the Terraform-shop review rules to project memory ([#55](https://github.com/jmcvetta/daily-driver/issues/55)) ([8b9a41d](https://github.com/jmcvetta/daily-driver/commit/8b9a41deb017c88ccdacc6b3242c1b14c3ef717c))

## [0.3.0](https://github.com/jmcvetta/daily-driver/compare/v0.2.0...v0.3.0) (2026-09-07)


### Features

* add the undertake skill, taking an issue to a ready pull request ([#49](https://github.com/jmcvetta/daily-driver/issues/49)) ([72c631d](https://github.com/jmcvetta/daily-driver/commit/72c631d0e4cbae31382259767c822524a172ee2b))


### Bug Fixes

* **agents:** inline the planning severity rubric into planning-fitness-reviewer ([#54](https://github.com/jmcvetta/daily-driver/issues/54)) ([f166c87](https://github.com/jmcvetta/daily-driver/commit/f166c87b7211c56a1c0c05c3430e56fc175a3088))
* **review:** correct the depth table's precedence and its worked example ([#39](https://github.com/jmcvetta/daily-driver/issues/39)) ([ce65c0c](https://github.com/jmcvetta/daily-driver/commit/ce65c0cbafe31aa278c239a7be9e0eb3c66b662b))

## [0.2.0](https://github.com/jmcvetta/daily-driver/compare/v0.1.0...v0.2.0) (2026-09-07)


### Features

* add the session-title skill ([#41](https://github.com/jmcvetta/daily-driver/issues/41)) ([0a98c36](https://github.com/jmcvetta/daily-driver/commit/0a98c36391e0297b0867a49934355bab3bfa1bf9))
* **judgement-call:** the gate before a choice is put to the user ([#44](https://github.com/jmcvetta/daily-driver/issues/44)) ([57abdf2](https://github.com/jmcvetta/daily-driver/commit/57abdf2b6260f40959bd33ac95d56a61bae9e946))
* retire pr-threads and review from the shipped skill panel ([#50](https://github.com/jmcvetta/daily-driver/issues/50)) ([03fc4b4](https://github.com/jmcvetta/daily-driver/commit/03fc4b4bfd11cb468c88ab9d2bf6c712c799e5d3))

## 0.1.0 (2026-09-06)


### Features

* add Makefile with git_sync target ([#4](https://github.com/jmcvetta/daily-driver/issues/4)) ([bc9ff38](https://github.com/jmcvetta/daily-driver/commit/bc9ff385dedef8692a2c8660f63364d09ab77d4d))
* deliver the constitution to sessions and subagents ([#31](https://github.com/jmcvetta/daily-driver/issues/31)) ([f4c57d1](https://github.com/jmcvetta/daily-driver/commit/f4c57d189073d00447de2a56247c8322a06a9e81))
* **issue-deps:** skill for GitHub issue relationships, with a curl script ([#26](https://github.com/jmcvetta/daily-driver/issues/26)) ([825c8ff](https://github.com/jmcvetta/daily-driver/commit/825c8ffda493eb338d22e3b2a2e06e04c53fb69e))
* manage repository settings with OpenTofu ([#5](https://github.com/jmcvetta/daily-driver/issues/5)) ([9b1ce0d](https://github.com/jmcvetta/daily-driver/commit/9b1ce0df6b005a52187cef41d3eebc7a7ce9f45c))
* **pr-threads:** the review-thread lifecycle skill ([#25](https://github.com/jmcvetta/daily-driver/issues/25)) ([11a4588](https://github.com/jmcvetta/daily-driver/commit/11a458894bd11439434cb13cfe34d0ff2ab96b12))
* **review:** collapse four review verbs into one skill ([#28](https://github.com/jmcvetta/daily-driver/issues/28)) ([d59021d](https://github.com/jmcvetta/daily-driver/commit/d59021d81d01f03c5dff97777fa6c53da24f0a1f))
* scaffold the plugin with the pr skill and an anti-license ([#3](https://github.com/jmcvetta/daily-driver/issues/3)) ([ea23bb0](https://github.com/jmcvetta/daily-driver/commit/ea23bb038b5d091fff3c1c0aae3cd3a93e97332e))
* **skills:** split pr into pr, pr-title and pr-body ([#27](https://github.com/jmcvetta/daily-driver/issues/27)) ([4440477](https://github.com/jmcvetta/daily-driver/commit/44404777a30d42c1476b46cbb010c4e9b3fa6874))
