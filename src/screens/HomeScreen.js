import React, { useEffect, useRef } from 'react';
import {
  Animated,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useNavigation } from '@react-navigation/native';

const FLOW_STEPS = [
  {
    title: 'Capture the magic',
    description:
      'Snap a soft, natural selfie so Allume can learn your undertones, textures, and glow goals.',
  },
  {
    title: 'Share your vibe',
    description:
      'Tell us how you are feeling, the event you are prepping for, or the energy you want to radiate.',
  },
  {
    title: 'Shop the edit',
    description:
      'Receive a stylist-approved routine with shades, products, and pro-level tips tailored to you.',
  },
];

const HomeScreen = () => {
  const navigation = useNavigation();
  const heroAnim = useRef(new Animated.Value(0)).current;
  const contentAnim = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    Animated.stagger(250, [
      Animated.timing(heroAnim, {
        toValue: 1,
        duration: 650,
        useNativeDriver: true,
      }),
      Animated.timing(contentAnim, {
        toValue: 1,
        duration: 650,
        useNativeDriver: true,
      }),
    ]).start();
  }, [heroAnim, contentAnim]);

  const heroStyle = {
    opacity: heroAnim,
    transform: [
      {
        translateY: heroAnim.interpolate({
          inputRange: [0, 1],
          outputRange: [28, 0],
        }),
      },
    ],
  };

  const contentStyle = {
    opacity: contentAnim,
    transform: [
      {
        translateY: contentAnim.interpolate({
          inputRange: [0, 1],
          outputRange: [24, 0],
        }),
      },
    ],
  };

  return (
    <LinearGradient colors={['#fff0f6', '#fff7fb', '#ffffff']} style={styles.gradient}>
      <SafeAreaView style={styles.safeArea}>
        <ScrollView
          contentContainerStyle={styles.scrollContent}
          showsVerticalScrollIndicator={false}
        >
          <Animated.View style={[styles.heroCard, heroStyle]}>
            <View style={styles.badge}>
              <Text style={styles.badgeText}>Allume Studio</Text>
            </View>
            <Text style={styles.kicker}>Digital beauty concierge</Text>
            <Text style={styles.title}>Your glow journey starts here ✨</Text>
            <Text style={styles.subtitle}>
              Meet the Allume tool—designed to capture your radiance, craft the perfect routine,
              and guide you with shoppable looks in minutes.
            </Text>
            <View style={styles.illustrationWrapper}>
              <View style={styles.auroraOne} />
              <View style={styles.auroraTwo} />
              <View style={styles.circle} />
            </View>
          </Animated.View>

          <Animated.View style={[styles.contentCard, contentStyle]}>
            <Text style={styles.sectionTitle}>Here’s the flow</Text>
            {FLOW_STEPS.map((step, index) => (
              <View key={step.title} style={styles.stepRow}>
                <View style={styles.stepIndex}>
                  <Text style={styles.stepIndexText}>{index + 1}</Text>
                </View>
                <View style={styles.stepCopy}>
                  <Text style={styles.stepTitle}>{step.title}</Text>
                  <Text style={styles.stepDescription}>{step.description}</Text>
                </View>
              </View>
            ))}

            <View style={styles.ctaGroup}>
              <TouchableOpacity
                style={styles.primaryCta}
                activeOpacity={0.9}
                onPress={() => navigation.navigate('Capture')}
              >
                <LinearGradient
                  colors={['#f672c5', '#f1488a']}
                  start={{ x: 0, y: 0 }}
                  end={{ x: 1, y: 1 }}
                  style={styles.primaryGradient}
                >
                  <Text style={styles.primaryLabel}>Capture Selfie</Text>
                  <Text style={styles.primarySubLabel}>Guided camera experience</Text>
                </LinearGradient>
              </TouchableOpacity>

              <TouchableOpacity
                style={styles.secondaryCta}
                activeOpacity={0.85}
                onPress={() => navigation.navigate('Upload')}
              >
                <Text style={styles.secondaryLabel}>Upload Photo</Text>
                <Text style={styles.secondarySubLabel}>Use an existing fave</Text>
              </TouchableOpacity>
            </View>
          </Animated.View>
        </ScrollView>
      </SafeAreaView>
    </LinearGradient>
  );
};

const styles = StyleSheet.create({
  gradient: {
    flex: 1,
  },
  safeArea: {
    flex: 1,
  },
  scrollContent: {
    paddingHorizontal: 24,
    paddingTop: 32,
    paddingBottom: 48,
  },
  heroCard: {
    backgroundColor: 'rgba(255, 255, 255, 0.75)',
    borderRadius: 28,
    padding: 24,
    overflow: 'hidden',
    shadowColor: '#f06292',
    shadowOpacity: 0.2,
    shadowRadius: 18,
    shadowOffset: { width: 0, height: 10 },
    elevation: 6,
    marginBottom: 32,
  },
  badge: {
    alignSelf: 'flex-start',
    backgroundColor: '#ffe0ef',
    borderRadius: 999,
    paddingHorizontal: 14,
    paddingVertical: 6,
    marginBottom: 12,
  },
  badgeText: {
    color: '#c2185b',
    fontSize: 12,
    fontWeight: '600',
    letterSpacing: 0.4,
  },
  kicker: {
    color: '#c2185b',
    fontSize: 14,
    fontWeight: '600',
    textTransform: 'uppercase',
    letterSpacing: 1.2,
    marginBottom: 8,
  },
  title: {
    color: '#55123b',
    fontSize: 28,
    fontWeight: '700',
    lineHeight: 34,
    marginBottom: 12,
  },
  subtitle: {
    color: '#6f3753',
    fontSize: 16,
    lineHeight: 22,
    marginBottom: 24,
  },
  illustrationWrapper: {
    height: 140,
    backgroundColor: '#ffeef7',
    borderRadius: 24,
    alignItems: 'center',
    justifyContent: 'center',
    overflow: 'hidden',
  },
  auroraOne: {
    position: 'absolute',
    width: 180,
    height: 180,
    borderRadius: 90,
    backgroundColor: 'rgba(255, 175, 204, 0.45)',
    top: -30,
    right: -20,
  },
  auroraTwo: {
    position: 'absolute',
    width: 160,
    height: 160,
    borderRadius: 80,
    backgroundColor: 'rgba(255, 214, 243, 0.65)',
    bottom: -20,
    left: -10,
  },
  circle: {
    width: 84,
    height: 84,
    borderRadius: 42,
    borderWidth: 2,
    borderColor: '#f06292',
    backgroundColor: 'rgba(255,255,255,0.7)',
  },
  contentCard: {
    backgroundColor: '#ffffff',
    borderRadius: 28,
    padding: 24,
    marginBottom: 24,
    shadowColor: '#f48fb1',
    shadowOpacity: 0.15,
    shadowRadius: 16,
    shadowOffset: { width: 0, height: 8 },
    elevation: 4,
  },
  sectionTitle: {
    fontSize: 20,
    fontWeight: '700',
    color: '#501437',
    marginBottom: 12,
  },
  stepRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    marginBottom: 18,
  },
  stepIndex: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: '#ffe4ef',
    alignItems: 'center',
    justifyContent: 'center',
  },
  stepIndexText: {
    color: '#c2185b',
    fontWeight: '700',
  },
  stepCopy: {
    flex: 1,
    marginLeft: 16,
  },
  stepTitle: {
    color: '#53173d',
    fontSize: 16,
    fontWeight: '600',
    marginBottom: 4,
  },
  stepDescription: {
    color: '#7a4763',
    lineHeight: 20,
  },
  ctaGroup: {
    marginTop: 12,
  },
  primaryCta: {
    borderRadius: 20,
    overflow: 'hidden',
    marginBottom: 16,
  },
  primaryGradient: {
    paddingVertical: 16,
    paddingHorizontal: 20,
    borderRadius: 20,
  },
  primaryLabel: {
    color: '#fff',
    fontSize: 18,
    fontWeight: '700',
  },
  primarySubLabel: {
    color: '#ffe1f2',
    marginTop: 2,
  },
  secondaryCta: {
    borderRadius: 20,
    borderWidth: 1,
    borderColor: '#f8b7d5',
    paddingVertical: 14,
    paddingHorizontal: 20,
    backgroundColor: '#fff7fc',
  },
  secondaryLabel: {
    color: '#b1035a',
    fontSize: 17,
    fontWeight: '600',
  },
  secondarySubLabel: {
    color: '#a04a7c',
    marginTop: 2,
  },
});

export default HomeScreen;
