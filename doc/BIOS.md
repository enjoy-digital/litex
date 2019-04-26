LiteX takes the philosophy of pushing as much onto the [[Soft CPU]] as possible. This means that most [[Gateware]] needs some accompanying code to initialize various settings and configurations. This specialized firmware is called the [[BIOS]].

The [[BIOS]] generally does tasks like;
 * Train any external DDR memory
 * Load the user's [[Firmware]] into external memory via;
   * Communication channels like serial, tftp 
   * Other storage systems like external flash.

This can make it very fast to do development as you can iterate on [[Firmware]] development quickly.