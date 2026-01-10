ENTRY(_start)
SECTIONS
{
  .text 0x00 : {
    *(.text)
  }
  .data : {
    *(.data)
  }
}
