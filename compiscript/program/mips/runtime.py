"""Hand-written support routines: everything MIPS has no instruction for.

``alloc`` is the one heap-shaped TAC op this stage *does* support, even
though arrays, objects and vtables (``load``/``store``/``calli``) stay out of
scope until the next stage. The reason is ``concat``/``tostr``: a chained
concatenation like ``"a" + b + "c"`` runs two separate ``concat`` quads, the
second reading the first's result — if both wrote into one shared scratch
buffer, the second call would overwrite the very bytes it is still reading,
and a string variable that captured the first result would silently change
later. A MIPS simulator's ``sbrk`` syscall (9) is already a real bump
allocator, so giving every ``concat``/``tostr`` result its own fresh memory
costs nothing extra to implement correctly.

Each routine is plain MIPS text, assembled once and appended to the end of
every generated program; the emitter only ever ``jal``s into it.
"""

from __future__ import annotations

ALLOC_LABEL = "__alloc"
TOSTR_INT_LABEL = "__tostr_int"
CONCAT_LABEL = "__concat"
PRINT_BOOL_LABEL = "__print_bool"

# Strings these routines reference; the emitter's ``.data`` section includes
# them once, regardless of whether the source program has any boolean print.
RUNTIME_DATA = f"""{PRINT_BOOL_LABEL}_true: .asciiz "true"
{PRINT_BOOL_LABEL}_false: .asciiz "false\""""

RUNTIME_TEXT = f"""{ALLOC_LABEL}:
    # $a0 = bytes requested -> $v0 = address of a fresh block.
    li $v0, 9
    syscall
    jr $ra

{TOSTR_INT_LABEL}:
    # $a0 = integer -> $v0 = address of its decimal text, freshly allocated.
    # $s2 holds "was negative" (0/1) for the whole routine, since $a0 itself
    # gets reused to pass the byte count to {ALLOC_LABEL} partway through —
    # anything that needs the sign later must not depend on reading $a0 or
    # the sign of the (by then already absolute-valued) $s0 again.
    addiu $sp, $sp, -36
    sw $ra, 0($sp)
    sw $s0, 4($sp)
    sw $s1, 8($sp)
    sw $s2, 12($sp)
    sw $s3, 16($sp)
    move $s0, $a0             # absolute value of the number, built below
    li $s2, 0                 # was negative?
    bgez $s0, {TOSTR_INT_LABEL}_digits
    li $s2, 1
    subu $s0, $zero, $s0
{TOSTR_INT_LABEL}_digits:
    li $s1, 0                 # digit count
    move $t1, $s0
{TOSTR_INT_LABEL}_count_loop:
    addi $s1, $s1, 1
    div $t1, $t1, 10
    bnez $t1, {TOSTR_INT_LABEL}_count_loop
    bnez $s0, {TOSTR_INT_LABEL}_count_done
    li $s1, 1                 # "0" itself still needs one digit
{TOSTR_INT_LABEL}_count_done:
    add $a0, $s1, $s2         # digits + (1 if negative)
    addi $a0, $a0, 1          # + NUL
    jal {ALLOC_LABEL}
    move $s3, $v0             # base of the buffer
    add $t3, $s3, $s1
    add $t3, $t3, $s2         # cursor: one past the last digit (the NUL slot)
    sb $zero, 0($t3)
    move $t1, $s0
{TOSTR_INT_LABEL}_emit_loop:
    addi $t3, $t3, -1
    div $t4, $t1, 10
    mul $t5, $t4, 10
    subu $t6, $t1, $t5        # t6 = t1 % 10
    addi $t6, $t6, 48         # ASCII '0'
    sb $t6, 0($t3)
    move $t1, $t4
    bnez $t1, {TOSTR_INT_LABEL}_emit_loop
    beqz $s2, {TOSTR_INT_LABEL}_done
    addi $t3, $t3, -1
    li $t6, 45                # ASCII '-'
    sb $t6, 0($t3)
{TOSTR_INT_LABEL}_done:
    move $v0, $s3
    lw $ra, 0($sp)
    lw $s0, 4($sp)
    lw $s1, 8($sp)
    lw $s2, 12($sp)
    lw $s3, 16($sp)
    addiu $sp, $sp, 36
    jr $ra

{CONCAT_LABEL}:
    # $a0, $a1 = two NUL-terminated strings -> $v0 = their concatenation,
    # freshly allocated.
    addiu $sp, $sp, -28
    sw $ra, 0($sp)
    sw $s0, 4($sp)
    sw $s1, 8($sp)
    sw $s2, 12($sp)
    sw $s3, 16($sp)
    sw $s4, 20($sp)
    move $s0, $a0
    move $s1, $a1
    move $t0, $s0
    li $s2, 0
{CONCAT_LABEL}_len1:
    lb $t1, 0($t0)
    beqz $t1, {CONCAT_LABEL}_len1_done
    addi $s2, $s2, 1
    addi $t0, $t0, 1
    b {CONCAT_LABEL}_len1
{CONCAT_LABEL}_len1_done:
    move $t0, $s1
    li $s3, 0
{CONCAT_LABEL}_len2:
    lb $t1, 0($t0)
    beqz $t1, {CONCAT_LABEL}_len2_done
    addi $s3, $s3, 1
    addi $t0, $t0, 1
    b {CONCAT_LABEL}_len2
{CONCAT_LABEL}_len2_done:
    add $a0, $s2, $s3
    addi $a0, $a0, 1
    jal {ALLOC_LABEL}
    move $s4, $v0
    move $t0, $s0
    move $t2, $s4
{CONCAT_LABEL}_copy1:
    lb $t1, 0($t0)
    beqz $t1, {CONCAT_LABEL}_copy1_done
    sb $t1, 0($t2)
    addi $t0, $t0, 1
    addi $t2, $t2, 1
    b {CONCAT_LABEL}_copy1
{CONCAT_LABEL}_copy1_done:
    move $t0, $s1
{CONCAT_LABEL}_copy2:
    lb $t1, 0($t0)
    sb $t1, 0($t2)
    beqz $t1, {CONCAT_LABEL}_copy2_done
    addi $t0, $t0, 1
    addi $t2, $t2, 1
    b {CONCAT_LABEL}_copy2
{CONCAT_LABEL}_copy2_done:
    move $v0, $s4
    lw $ra, 0($sp)
    lw $s0, 4($sp)
    lw $s1, 8($sp)
    lw $s2, 12($sp)
    lw $s3, 16($sp)
    lw $s4, 20($sp)
    addiu $sp, $sp, 28
    jr $ra

{PRINT_BOOL_LABEL}:
    # $a0 = 0 or 1 -> prints "false"/"true"; no return value. The branch
    # targets below are code labels, kept distinct from the two data labels
    # ({PRINT_BOOL_LABEL}_true/_false, declared in RUNTIME_DATA) they load
    # the address of — reusing one name for both would collide.
    beqz $a0, {PRINT_BOOL_LABEL}_is_false
    la $a0, {PRINT_BOOL_LABEL}_true
    b {PRINT_BOOL_LABEL}_print
{PRINT_BOOL_LABEL}_is_false:
    la $a0, {PRINT_BOOL_LABEL}_false
{PRINT_BOOL_LABEL}_print:
    li $v0, 4
    syscall
    jr $ra
"""
