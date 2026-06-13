import inspect
import backpropagate
from backpropagate import Trainer

print("pkg:", backpropagate.__file__)
print("Trainer init params:", list(inspect.signature(Trainer.__init__).parameters))
print("train params:", list(inspect.signature(Trainer.train).parameters))
src = inspect.getsource(type(Trainer.train)) if False else inspect.getsourcefile(Trainer)
print("source file:", src)
# find where the peft model is built
import re
code = open(src).read()
for m in re.finditer(r".*(get_peft_model|PeftModel|resume_from_checkpoint|init_lora|load_adapter).*", code):
    print(">>", m.group(0).strip()[:120])
