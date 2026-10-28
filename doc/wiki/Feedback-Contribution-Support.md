## **Feedback / Contribution / Support**

Feedback, contributions greatly help improving open-source projects and any contribution to LiteX is welcome:
- You create a design with LiteX, **it works** and you are happy with it? Please **let us know**, we could list it as a [useful resource](Tutorials-Resources.md#examples-to-read) or a [project](Projects.md)! It could be used as an example and help other users.
- You try to use LiteX but it **does not work**, we could certainly help if you create an **issue**, but please have a look at the list of **things we'll need to know** to be able to help you.
- You've seen things that could be **improved** or have some **ideas** you think would be useful for the project? **Please share it with us**. If you don't feel confident enough to modify the code yourself, feel free to **create an issue describing your idea(s)** and describe how it could improve the project. If you think you are able to do the modification yourself, feel free to **try and create a Pull Request**. Even if this is not perfect, this would be welcomed and we will help you understand how you could eventually improve it or could do the modification for you. 
- The documentation is wrong, outdated or missing something? This wiki is generated from the `doc/wiki` directory of the LiteX repository: [send a pull request](Contributing-to-the-Wiki.md), even for a one line fix.

It's also possible you will think of things we would never have figured out ourselves or things you are expert in and would implement better than us and that's what we think make open-source so rewarding: **everyone learn from each other**!

We think LiteX could be useful and offer some innovative solutions for some projects, but we are also aware it's not perfect and/or will not be the solution for everyone/every project. If you are interested by the project and **want to contribute, please do!**, if the only thing that works for you with LiteX is making you angry, we're not sure the right project is for you :) (but are open to constructive criticism).

## **How to create an issue when you just have an idea?**

Please **just feel free to create an issue to share your idea with us**, if you also have ideas on the implementation,  we encourage you to try it (that's how you'll learn and progress!) and submit it in the issue or even in a PR. LiteX community is **very welcoming** and we could give you directions/advices to implement your idea or do the implementation ourselves if that's something interesting for the whole project.

## **How to create an issue when it does not work?**

LiteX provides [tutorials](Tutorials-Resources.md), examples of [projects](Projects.md) and default [platforms/targets](https://github.com/litex-hub/litex-boards) for very various FPGA boards. These ones have been tested/validated and most of them covered by our CI. 

Since LiteX **possibilities are infinite**,  it's not possible for us to support or test all combinations. The codebase can have some wanted limitations (because we don't have a need for this yet and haven't implemented this combination) or issues that are not. FPGA are also constraints in size/speed and constraints can also come from there. We are happy to have your feedback on eventual issues/limitations you could have identified, but please consider that analyzing, fixing it or adding support new features requires a minimum amount of information and time, so if you want us to take time to look at the issue, please also **take a bit of your time to prepare the issue**, "**it does not work**" is **not enough** :) Quite often the solution to complex issues is in small details, having enough information from the start could avoid quite some back and forth in the communication and save days!

If you are testing some example code with specific parameters that you think should be supported, please share with us (if you think that's relevant):
 - Your test environment.
 - The target/example you are building.
 - The specific parameters you eventually added.
 - The logs LiteX generate (during the build, on the console, from the toolchains).
 - The timing report of your design.

If you are testing a design you created with the tools or developing  a new feature and have troubles, in addition to the previous information, the best is generally to create a minimal reproduction of the issue and share it with us. This allows us to reproduce the issue and have all the information we need to investigate without having to ask you each time we progress. 

**Reading this is the first thing we'll ask you if your issue does not provide enough information, so  you please try to anticipate :)**

## **How to create a Pull Request?**

If you **have an idea** and think you can **implement it**, please go ahead, **that's how you'll learn and progress!** We encourage you to do so and will **always welcome contributions**, we can help to make sure it can be merged if useful for the whole project. If before doing the hard work you have doubts it will be possible to merge your work since maybe not useful for the whole project or too specific, please feel free to first create an issue to discuss this.

Please use a coding style close to the already existing files: the [coding style](https://github.com/enjoy-digital/litex/blob/master/doc/coding_style.md) and [architectural style](https://github.com/enjoy-digital/litex/blob/master/doc/architectural_style.md) documents describe it (file layout, HDL conventions, where a device-specific piece of code belongs), with commit messages of the form `module: Description of the change.`. Say in the pull request what was tested (simulation, which board) and what was not.

## **Support**

While LiteX is an open-source project and we are really enjoying working on it, the team doing the development/maintenance is still small and often have others obligations since the initial goal of LiteX was to create custom FPGA based systems with it, so please understand if we need a few days to respond. The community is also growing and helping: join us on [Discord](https://discord.gg/PkJwjDbxeG) or on IRC at [#litex at irc.libera.chat](https://web.libera.chat/#litex).

We have the chance to have clients trusting us and funding systems built with LiteX or new developments but please consider that most of us can only answer you on working days and also need to spend weekend/holidays with our family and friends to come back with fresh minds and ideas!

We are happy to provide basic support for everyone, if you are developing a product, want to reuse LiteX or part of it (some of the cores, the infrastructure, etc...) and want extensive support or want us to customize things for you, please get in touch with us, seeing our work used on real products it what motivate us and we'll see together what we and our partners could do!

## Community

<p align="center"><img src="https://raw.githubusercontent.com/enjoy-digital/litex/master/doc/litex-hub.png" width="400"></p>

Over the years a friendly community has grown around LiteX and the ecosystem of cores. Feedbacks and contributions have already greatly improved the project, EnjoyDigital still leads the development but it is now a community project and collaborative projects created around/with LiteX can be found at https://github.com/litex-hub.


Contact: florent@enjoy-digital.fr
