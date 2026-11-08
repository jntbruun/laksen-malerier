package no.laksen.stonecutter.mixin;

import net.minecraft.client.gui.screens.inventory.StonecutterScreen;
import net.minecraft.world.item.Item;
import net.minecraft.world.item.ItemStack;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Shadow;
import org.spongepowered.asm.mixin.Unique;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

/**
 * Vanilla scrolls the recipe list back to the top every time the input slot changes,
 * including when you take a result (the count drops) or the server resyncs the slot.
 * With dozens of paintings that means scrolling back down after every pick.
 * Here the list only resets when a different kind of item goes in.
 */
@Mixin(StonecutterScreen.class)
public abstract class StonecutterScreenMixin {
    @Shadow private float scrollOffs;
    @Shadow private int startIndex;
    @Shadow private boolean displayRecipes;

    @Unique private Item laksen$lastItem;
    @Unique private float laksen$savedScrollOffs;
    @Unique private int laksen$savedStartIndex;
    @Unique private boolean laksen$restoreAfterEmpty;

    @Inject(method = "containerChanged", at = @At("HEAD"), cancellable = true)
    private void laksen$keepScrollPosition(CallbackInfo ci) {
        ItemStack input = ((StonecutterScreen) (Object) this).getMenu().getSlot(0).getItem();

        if (input.isEmpty()) {
            // Took the last one: remember where we were, in case the same item goes back in.
            if (displayRecipes) {
                laksen$savedScrollOffs = scrollOffs;
                laksen$savedStartIndex = startIndex;
                laksen$restoreAfterEmpty = true;
            }
            return; // vanilla hides the list
        }

        if (input.getItem() == laksen$lastItem) {
            displayRecipes = true;
            if (laksen$restoreAfterEmpty) {
                scrollOffs = laksen$savedScrollOffs;
                startIndex = laksen$savedStartIndex;
                laksen$restoreAfterEmpty = false;
            }
            ci.cancel();
            return;
        }

        // A different item: different recipes, so starting from the top is right.
        laksen$lastItem = input.getItem();
        laksen$restoreAfterEmpty = false;
    }
}
