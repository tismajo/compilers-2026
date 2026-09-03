let amount: float = 10.5;
class Box {
  let value: float;
  function constructor(value: float) {
    this.value = value;
  }
}
let box: Box = new Box(amount);
box.value = 12.25;
