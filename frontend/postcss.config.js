import postcssJitProps from 'postcss-jit-props';
import postcssCustomMedia from 'postcss-custom-media';
import OpenProps from 'open-props';

export default {
  plugins: [postcssJitProps(OpenProps), postcssCustomMedia()],
};
